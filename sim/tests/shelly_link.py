#!/usr/bin/env python3
"""The link to the Shelly: 5 s rule, failures, recovery, time from the Shelly.

    python3 sim/tests/shelly_link.py      (about 2 minutes)
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (check, finish, get, post, sim, sim_state, start, status,  # noqa: E402
                    stop, wait_for)

p = start("--reset-sd", "--shelly-time")
try:
    print("Time from the Shelly")
    s = wait_for(lambda s: s["rtc_synced"], 20)
    check(s["rtc_synced"] and s["time_source"] == "shelly", "clock taken from the Shelly")
    lt = time.localtime()
    # utc_offset is 7200 seconds in the model; the old code would have been
    # 7200 hours off.
    check(s["time"][:13] == f"{lt.tm_year}-{lt.tm_mon:02d}-{lt.tm_mday:02d} {lt.tm_hour:02d}",
          f"Shelly time correct to the hour ({s['time']})")

    print("5 s rule")
    sim("clear_requests")
    for _ in range(3):                      # commands mixed into polling
        post("/toggle_shelly")
        time.sleep(0.3)
    time.sleep(25)
    st = sim_state()
    check(st["min_gap_s"] is not None and st["min_gap_s"] >= 0.95,
          f"never two requests within 1 s (min gap {st['min_gap_s']} s)")
    # Gaps before a status poll must be >= 5 s
    print("  methods:", st["shelly_methods"])

    print("Shelly does not answer")
    sim("shelly_offline", v="1")
    s = wait_for(lambda s: not s["shelly_ok"], 20)
    check(not s["shelly_ok"] and s["shelly_state"] == "offline", "failure detected")
    s = status()
    check(s["loop_dt_max"] < 6, f"server loop stays responsive ({s['loop_dt_max']:.1f} s max)")
    sim("shelly_offline", v="0")
    s = wait_for(lambda s: s["shelly_ok"], 20)
    check(s["shelly_ok"], "recovered")
    log = get("/error_log")
    check("SHELLY unreachable" in log and "SHELLY reachable again" in log,
          "failure and recovery in the error log")

    print("Shelly Wi-Fi gone")
    sim("wifi_off", v="1")
    s = wait_for(lambda s: s["sta_ip"] is None, 20)
    check(s["sta_ip"] is None, "loss of the Shelly Wi-Fi detected")
    check(status()["ap_ip"] == "192.168.4.1", "own AP keeps running")
    sim("wifi_off", v="0")
    s = wait_for(lambda s: s["shelly_ok"], 60)
    check(s["shelly_ok"] and s["sta_ip"], "reconnected to the Shelly")
    check("SHELLY WIFI lost" in get("/error_log"), "loss in the error log")

    st = sim_state()
    check(st["open_responses"] == 0, "no open HTTP responses (socket leak)")
    check(st["watchdog_trips"] == 0, "watchdog never tripped")
finally:
    stop(p)
finish()
