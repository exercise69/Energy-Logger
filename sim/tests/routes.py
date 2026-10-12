#!/usr/bin/env python3
"""Every route answers, the clock is set from the phone, logs can be downloaded.

    python3 sim/tests/routes.py      (about 30 seconds)
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (check, finish, get, post, sim_state, start, status, stop,  # noqa: E402
                    wait_for)

p = start("--reset-sd")
try:
    print("Start")
    s = wait_for(lambda s: s["shelly_ok"], 20)
    check(s["shelly_ok"], "Shelly reached")
    check(not s["rtc_synced"], "clock unset after boot")
    check(s["version"] and s["build"] > 0, f"version in status.json ({s['version']} b{s['build']})")
    check("BOOT  v" in get("/error_log"), "BOOT line in the error log")

    print("Static files")
    for path in ("/", "/app.js", "/style.css", "/manifest.json", "/service-worker.js",
                 "/offline.html", "/ping"):
        try:
            get(path)
            ok = True
        except Exception:
            ok = False
        check(ok, f"GET {path}")

    print("Clock")
    code, d = post("/set_time", {"epoch": int(time.time())})
    check(code == 200 and d["ok"], "set_time with the phone's epoch")
    s = status()
    check(s["rtc_synced"] and s["time_source"] == "phone", "clock set, source phone")
    lt = time.localtime()
    check(s["time"][:10] == f"{lt.tm_year}-{lt.tm_mon:02d}-{lt.tm_mday:02d}",
          f"local date correct ({s['time']})")
    code, d = post("/set_time", {"dt": "nonsense"})
    check(code == 400 and not d["ok"], "bad manual time is rejected")
    time.sleep(2)
    check("Sys.SetTime" in sim_state()["shelly_methods"], "time sent to the Shelly")

    print("Switching")
    before = status()["output"]
    post("/toggle_shelly")
    s = wait_for(lambda s: s["output"] != before, 5)
    check(s["output"] != before, "toggle switches the plug")
    check(sim_state()["shelly"]["output"] == s["output"], "Shelly model agrees")

    print("Logging")
    s = wait_for(lambda s: s["sd_log_size"] > 100, 20)
    files = __import__("json").loads(get("/log_files"))
    check(any(f["file"] == "energy_log.csv" for f in files), "log_files lists energy_log.csv")
    body = get(f"/log_stream?file=energy_log.csv&offset=0&end={files[0]['size']}")
    check(body.startswith("time,power_w,energy_wh,output"), "download starts with the header")
    check(len(body.encode()) == files[0]["size"], "download has the full size")
    try:
        get("/log_stream?file=../config.py")
        check(False, "foreign path rejected")
    except Exception:
        check(True, "foreign path rejected")
    code, d = post("/toggle_logging")
    check(d.get("logging_enabled") is False, "logging can be switched off")
    post("/toggle_logging")

    print("Diagnostics")
    check("(no health log)" in get("/health_log") or "time,free_b" in get("/health_log"),
          "health_log answers")
    code, d = post("/remount_sd")
    check(d.get("ok"), "remount_sd")
    st = sim_state()
    check(st["open_responses"] == 0, "no open HTTP responses (socket leak)")
    check(st["watchdog_trips"] == 0, "watchdog never tripped")
finally:
    stop(p)
finish()
