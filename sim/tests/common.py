"""Helpers shared by the simulator tests."""

import json
import os
import signal
import subprocess
import sys
import time
import urllib.parse
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SD = os.path.join(REPO, "sim", "sd")
DEVICE = "http://127.0.0.1:8080"
PANEL = "http://127.0.0.1:8081"

failures = []


def check(condition, text):
    print(f"  {'OK  ' if condition else 'FAIL'} {text}")
    if not condition:
        failures.append(text)


def get(path, timeout=15):
    with urllib.request.urlopen(DEVICE + path, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def post(path, data=None):
    body = urllib.parse.urlencode(data or {}).encode()
    req = urllib.request.Request(DEVICE + path, data=body, method="POST", headers={
        "Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def status():
    return json.loads(get("/status.json"))


def sim(action, **params):
    q = urllib.parse.urlencode({"action": action, **params})
    with urllib.request.urlopen(f"{PANEL}/sim/api?{q}", timeout=10) as r:
        return json.loads(r.read())


def sim_state():
    with urllib.request.urlopen(f"{PANEL}/sim/state", timeout=10) as r:
        return json.loads(r.read())


def wait_for(condition, seconds=60):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        s = status()
        if condition(s):
            return s
        time.sleep(1)
    return status()


def start(*args):
    stop_leftovers()
    p = subprocess.Popen([sys.executable, "-u", "sim/run_sim.py", *args], cwd=REPO,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
    for _ in range(60):
        time.sleep(0.5)
        try:
            status()
            return p
        except Exception:
            pass
    stop(p)
    raise SystemExit("simulator did not come up")


def stop(p):
    try:
        os.killpg(os.getpgid(p.pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        pass
    time.sleep(1)
    stop_leftovers()


def stop_leftovers():
    """A simulator restarted by microcontroller.reset() has a new PID."""
    for port in (8080, 8081):
        pids = subprocess.run(["lsof", "-ti", f"tcp:{port}", "-sTCP:LISTEN"],
                              capture_output=True, text=True).stdout.split()
        for pid in pids:
            if int(pid) != os.getpid():
                try:
                    os.kill(int(pid), signal.SIGKILL)
                except Exception:
                    pass
    time.sleep(0.5)


def sd_lines(name="energy_log.csv"):
    try:
        with open(os.path.join(SD, name)) as f:
            return f.read().splitlines()
    except OSError:
        return []


def finish():
    print()
    if failures:
        print(f"{len(failures)} FAILED:")
        for f in failures:
            print("  - " + f)
        sys.exit(1)
    print("all checks passed")
