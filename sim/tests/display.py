#!/usr/bin/env python3
"""Display detection: SSD1306 128x64 vs SSD1327 128x128 on the same address.

    python3 sim/tests/display.py      (about 1 minute)

Part 1 checks classify_display() from code.py directly with status bytes.
Part 2 boots the simulator with each display and checks driver, size,
status.json, the BOOT line and the test pattern.
"""

import ast
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (REPO, check, finish, get, post, sim_state, start, status,  # noqa: E402
                    stop, wait_for)

print("Status byte classification")
src = open(os.path.join(REPO, "code.py")).read()
fn = [n for n in ast.parse(src).body
      if isinstance(n, ast.FunctionDef) and n.name == "classify_display"]
ns = {}
exec(compile(ast.Module(body=fn, type_ignores=[]), "code.py", "exec"), ns)
classify = ns["classify_display"]
check(classify(0x02) == "ssd1327", "0x02 -> SSD1327 (measured on the device)")
check(classify(0x03) == "ssd1306", "0x03 -> SSD1306 (display on)")
check(classify(0x43) == "ssd1306", "0x43 -> SSD1306 (display off)")
check(classify(0x06) == "ssd1306", "0x06 -> SSD1306 (variant)")
check(classify(None) is None, "no status byte -> unknown")
check(classify(0x5A) is None, "other byte -> unknown")

CASES = [
    ("ssd1306", "ssd1306", "auto", [128, 64]),
    ("ssd1327", "ssd1327", "auto", [128, 128]),
    ("unknown", "ssd1306", "fallback", [128, 64]),
    ("none", "none", None, None),
]

for sim_kind, want, how, size in CASES:
    print(f"Simulator with display '{sim_kind}'")
    p = start("--reset-sd", "--display", sim_kind)
    try:
        s = wait_for(lambda s: s["shelly_ok"], 20)
        check(s["display"] == want, f"status.json display = {s['display']}")
        if how:
            check(s["display_how"] == how, f"detection = {s['display_how']}")
        st = sim_state()
        if size:
            check(st["display_driver"] == want, f"driver {st['display_driver']}")
            check(st["display_size"] == size, f"size {st['display_size']}")
        else:
            check(st["display_driver"] is None, "no driver started")
        check(f"display={want}" in get("/error_log"), "display in the BOOT line")
        code, d = post("/display_test")
        check(d.get("ok") == bool(size), "display_test answers")
        if size:
            time.sleep(4)          # after the 3 s boot splash
            check("DISPLAY-TEST" in sim_state()["display"], "test pattern shown")
        check(status()["shelly_ok"], "logger keeps running")
    finally:
        stop(p)

finish()
