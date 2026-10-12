#!/usr/bin/env python3
"""Energy-Logger simulator.

Runs the real code.py on the Mac. Hardware is replaced by stand-ins, the
Shelly by a model. code.py, config.py and html/ are not changed.

    python3 sim/run_sim.py
    python3 sim/run_sim.py --reset-sd --no-sd

Then:
    http://127.0.0.1:8080/   the device's web UI (the real html/)
    http://127.0.0.1:8081/   simulator control panel
"""

import argparse
import importlib.util
import os
import sys
import time

# CircuitPython has no time zones: localtime() is UTC there. Same here.
os.environ["TZ"] = "UTC"
time.tzset()

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from simlib import fs, httpserver, shelly, shims      # noqa: E402

SIM_SECRETS = {
    "ap_ssid": "Energy-Logger",
    "ap_password": "simulator",
    "shelly_ap_ssid": "ShellyPlusPlugS-SIM",
    "shelly_ap_password": "simulator",
}


def parse_args():
    p = argparse.ArgumentParser(description="Energy-Logger simulator")
    p.add_argument("--port", type=int, default=8080, help="port of the web UI")
    p.add_argument("--shelly-port", type=int, default=8081,
                   help="port of the Shelly model and the control panel")
    p.add_argument("--poll", type=int, default=5, help="poll_interval for the Shelly")
    p.add_argument("--load", type=float, default=60.0, help="load on the plug in W")
    p.add_argument("--shelly-time", action="store_true", help="Shelly already has a time")
    p.add_argument("--no-sd", action="store_true", help="start without an SD card")
    p.add_argument("--reset-sd", action="store_true", help="empty the stand-in SD card")
    return p.parse_args()


def load_config(args):
    """The real config.py, with the Shelly address pointed at the model."""
    spec = importlib.util.spec_from_file_location("el_config", os.path.join(REPO, "config.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    cfg = dict(mod.config)
    cfg["shelly_ip"] = "shelly.sim"
    cfg["poll_interval"] = args.poll
    cfg["health_interval"] = 20          # short in the simulator, 300 on the device
    return cfg


def main():
    args = parse_args()
    fs.setup(REPO, HERE)
    httpserver.PORT = args.port
    if args.reset_sd:
        for name in os.listdir(fs.sd_root()):
            p = os.path.join(fs.sd_root(), name)
            if os.path.isfile(p):
                os.remove(p)
        print("[SIM] stand-in SD card emptied")

    plug = shelly.Shelly(load_w=args.load, has_time=args.shelly_time)
    state = {
        "shelly": plug,
        "shelly_addr": "shelly.sim",
        "shelly_port": args.shelly_port,
        "shelly_offline": False,
        "wifi_off": False,
        "sd_present": not args.no_sd,
        "reset_reason": ("SOFTWARE" if os.environ.pop("ENERGY_LOGGER_SIM_RESET", None)
                         else "POWER_ON"),
    }

    def describe():
        reqs = state["shelly_requests"]
        gaps = [b[0] - a[0] for a, b in zip(reqs, reqs[1:])]
        disp = state.get("display")
        lines = [l.text for l in (disp.root_group or [])] if disp else []
        return {
            "shelly": {"output": plug.output, "energy_wh": round(plug.energy_wh, 3),
                       "load_w": plug.load_w, "has_time": plug.has_time,
                       "offline": state["shelly_offline"]},
            "wifi_off": state["wifi_off"],
            "sd_present": state["sd_present"], "sd_mounted": fs.sd_mounted,
            "shelly_requests": len(reqs),
            "shelly_methods": [m for _, m in reqs[-10:]],
            "min_gap_s": round(min(gaps), 2) if gaps else None,
            "open_responses": state["open_responses"](),
            "watchdog_trips": state["watchdog_trips"],
            "led": state.get("led"),
            "display": lines,
        }

    def action(name, params):
        v = params.get("v") == "1"
        if name == "shelly_offline":
            state["shelly_offline"] = v
        elif name == "wifi_off":
            state["wifi_off"] = v
            if v:
                state["radio"].connected = False
                state["radio"].ipv4_address = None
        elif name == "sd_remove":
            state["sd_present"] = False
            fs.sd_mounted = False
        elif name == "sd_insert":
            state["sd_present"] = True
        elif name == "sd_fail_after_write":
            fs.fail_after_write = int(params.get("n", 1))
        elif name == "shelly_time":
            plug.has_time = v
        elif name == "load":
            plug.load_w = float(params.get("w", 60))
        elif name == "set_rtc":
            shims.set_rtc(float(params["epoch"]))
        elif name == "clear_requests":
            state["shelly_requests"].clear()
        else:
            raise ValueError(f"unknown action {name}")

    state["describe"] = describe
    state["action"] = action

    shims.install(state, os.path.join(fs.device_root(), "nvm.bin"),
                  SIM_SECRETS, load_config(args))
    shelly.start(state, args.shelly_port, args.port)

    print("=" * 60)
    print("  Energy-Logger simulator")
    print(f"  Web UI        : http://127.0.0.1:{args.port}/")
    print(f"  Control panel : http://127.0.0.1:{args.shelly_port}/")
    print("=" * 60)

    spec = importlib.util.spec_from_file_location("energy_logger_code",
                                                  os.path.join(REPO, "code.py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules["energy_logger_code"] = module
    try:
        spec.loader.exec_module(module)          # runs until Ctrl-C
    except KeyboardInterrupt:
        print("\n[SIM] stopped")


if __name__ == "__main__":
    main()
