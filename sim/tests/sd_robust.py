#!/usr/bin/env python3
"""SD card: missing card, card inserted later, write errors, month rotation.

    python3 sim/tests/sd_robust.py      (about 1.5 minutes)
"""

import calendar
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (check, finish, post, sd_lines, sim, start, status, stop,  # noqa: E402
                    wait_for)

p = start("--reset-sd", "--no-sd")
try:
    print("Boot without a card")
    s = wait_for(lambda s: s["shelly_ok"], 20)
    check(s["sd_status"] == "error", "status error without a card")
    check(s["shelly_ok"], "measuring continues without a card")

    print("Card inserted later")
    sim("sd_insert")
    s = wait_for(lambda s: s["sd_status"] == "ok" and s["sd_log_size"] > 0, 30)
    check(s["sd_status"] == "ok", "card mounted automatically (no 'in use' error)")
    check(len(sd_lines()) >= 2, "queued lines written after insert")

    print("Card pulled while running")
    sim("sd_remove")
    s = wait_for(lambda s: s["sd_status"] == "error", 20)
    check(s["sd_status"] == "error", "loss detected")
    sim("sd_insert")
    s = wait_for(lambda s: s["sd_status"] == "ok" and s["sd_queue_len"] == 0, 30)
    check(s["sd_status"] == "ok" and s["sd_queue_len"] == 0, "remounted, queue empty")

    print("Driver error after the write")
    post("/set_time", {"epoch": int(time.time())})
    sim("sd_fail_after_write", n="3")
    time.sleep(25)
    data = [l for l in sd_lines()[1:] if not l.startswith("T+")]
    stamps = [l.split(",")[0] for l in data]
    check(len(stamps) == len(set(stamps)), f"no duplicate lines ({len(stamps)} lines)")
    s = wait_for(lambda s: s["sd_status"] == "ok", 20)
    check(s["sd_status"] == "ok", "status back to ok after a good write")
    check(s["sd_error_count"] >= 1 and s["sd_error_txt"], "error text in status.json")

    print("Month rotation")
    # The RTC holds local time; the simulator renders it in UTC, so timegm
    sim("set_rtc", epoch=str(calendar.timegm((2026, 11, 30, 23, 59, 40, 0, 0, 0))))
    time.sleep(35)
    check(os.path.exists(os.path.join(os.path.dirname(__file__), "..", "sd",
                                      "energy_log_2026-11.csv")),
          "energy_log_2026-11.csv created")
    lines = sd_lines()
    check(lines and lines[0].startswith("time,") and
          all(l.startswith("2026-12") for l in lines[1:]),
          "new energy_log.csv starts with header and only December lines")
finally:
    stop(p)
finish()
