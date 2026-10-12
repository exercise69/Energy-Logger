#!/usr/bin/env python3
"""Unit test: CET/CEST offset and local<->UTC conversion from code.py.

    python3 sim/tests/dst.py      (instant, no simulator needed)

The functions are taken from code.py via ast, so the real code is tested.
"""

import ast
import os
import sys
import time

os.environ["TZ"] = "UTC"          # CircuitPython localtime() is UTC
time.tzset()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import REPO, check, finish      # noqa: E402

src = open(os.path.join(REPO, "code.py")).read()
wanted = {"_cet_offset_hours", "local_to_utc"}
funcs = [n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name in wanted]
ns = {"time": time}
exec(compile(ast.Module(body=funcs, type_ignores=[]), "code.py", "exec"), ns)
offset, local_to_utc = ns["_cet_offset_hours"], ns["local_to_utc"]


def utc(*t):
    return int(time.mktime((*t, 0, 0, -1)))


print("CET/CEST offset")
check(offset(utc(2026, 1, 15, 12, 0, 0)) == 1, "January = CET (+1)")
check(offset(utc(2026, 7, 15, 12, 0, 0)) == 2, "July = CEST (+2)")
check(offset(utc(2026, 3, 29, 0, 59, 0)) == 1, "29.03.2026 00:59 UTC still CET")
check(offset(utc(2026, 3, 29, 1, 0, 0)) == 2, "29.03.2026 01:00 UTC switches to CEST")
check(offset(utc(2026, 3, 22, 12, 0, 0)) == 1, "Sunday before the switch is CET")
check(offset(utc(2026, 10, 25, 0, 59, 0)) == 2, "25.10.2026 00:59 UTC still CEST")
check(offset(utc(2026, 10, 25, 1, 0, 0)) == 1, "25.10.2026 01:00 UTC back to CET")
check(offset(utc(2027, 3, 28, 1, 0, 0)) == 2, "2027: last Sunday is 28.03.")

print("local -> UTC")
check(local_to_utc(utc(2026, 7, 1, 14, 0, 0)) == utc(2026, 7, 1, 12, 0, 0),
      "14:00 CEST = 12:00 UTC")
check(local_to_utc(utc(2026, 12, 1, 14, 0, 0)) == utc(2026, 12, 1, 13, 0, 0),
      "14:00 CET = 13:00 UTC")

finish()
