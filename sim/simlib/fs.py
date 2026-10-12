"""Path mapping: device paths -> folders in the simulator.

code.py opens files under "/sd/...", "/html/..." and "/boot_out.txt". Those
paths do not exist on the Mac. Instead of touching code.py, open() and the
os functions it uses are redirected.

    /sd/...     -> sim/sd/...      (stand-in SD card, only while "mounted")
    /html/...   -> <repo>/html/... (the real web UI)
    /<file>     -> sim/device/...  (device root; protects the real code.py)

Everything else is left alone — in particular real Mac paths.
"""

import builtins
import errno
import os

REPO = None
SIM = None

_real_open = builtins.open
_real_stat = os.stat
_real_remove = os.remove
_real_listdir = os.listdir
_real_rename = os.rename

# Set by the storage shim: the stand-in card is only reachable while mounted,
# as on the device.
sd_mounted = False

# Field fault seen on the SolarLoader with sdcardio: the line reaches the
# card, *then* the driver reports an error. This many of the next writes to
# /sd/... fail on close (control panel: action=sd_fail_after_write&n=3).
fail_after_write = 0


def dev(path):
    """Map a device path to the matching folder in the simulator."""
    if not isinstance(path, str) or not path.startswith("/"):
        return path
    if path == "/sd" or path.startswith("/sd/"):
        if not sd_mounted:
            raise OSError(errno.ENODEV, "SD card not mounted")
        return os.path.join(SIM, "sd") + path[3:]
    if path == "/html" or path.startswith("/html/"):
        return os.path.join(REPO, "html") + path[5:]
    rest = path[1:]
    if rest and "/" not in rest:
        return os.path.join(SIM, "device", rest)
    return path


def sd_root():
    return os.path.join(SIM, "sd")


def device_root():
    return os.path.join(SIM, "device")


class _FailOnClose:
    def __init__(self, f):
        self._f = f

    def __getattr__(self, name):
        return getattr(self._f, name)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()
        return False

    def close(self):
        self._f.close()                          # data is on the card ...
        raise OSError(5, "Input/output error")   # ... but the driver reports an error


def _open(file, *a, **kw):
    global fail_after_write
    f = _real_open(dev(file), *a, **kw)
    mode = a[0] if a else kw.get("mode", "r")
    if (fail_after_write > 0 and isinstance(file, str) and file.startswith("/sd/")
            and any(c in mode for c in "wa")):
        fail_after_write -= 1
        return _FailOnClose(f)
    return f


def setup(repo_dir, sim_dir):
    """Activate the redirection. Must run before code.py is imported."""
    global REPO, SIM
    REPO, SIM = repo_dir, sim_dir
    os.makedirs(sd_root(), exist_ok=True)
    os.makedirs(device_root(), exist_ok=True)

    builtins.open = _open
    os.stat = lambda p, *a, **kw: _real_stat(dev(p), *a, **kw)
    os.remove = lambda p, *a, **kw: _real_remove(dev(p), *a, **kw)
    os.listdir = lambda p=".", *a, **kw: _real_listdir(dev(p), *a, **kw)
    os.rename = lambda a, b, *x, **kw: _real_rename(dev(a), dev(b), *x, **kw)

    bo = os.path.join(device_root(), "boot_out.txt")
    if not os.path.exists(bo):
        with _real_open(bo, "w") as f:
            f.write("Adafruit CircuitPython (simulation) on macOS\n"
                    "Board ID:energy_logger_sim\n")
