"""CircuitPython stand-ins for CPython.

Every module code.py imports that does not exist on the Mac is rebuilt here
and put into sys.modules — before code.py is imported. code.py itself stays
unchanged.

Some stand-ins are deliberately strict, so the simulator finds the bugs the
device would hit:
  - a pin can be claimed only once ("A1 in use"), as in CircuitPython
  - unclosed HTTP responses are counted (socket leak)
  - the watchdog is watched: a loop that is not fed in time is recorded
  - the RTC starts at 2000-01-01 and time.time() follows it, as on the device
"""

import errno
import sys
import threading
import time
import types
import urllib.error
import urllib.request

from . import fs, httpserver

_state = None
_real_time = time.time


def _mod(name, **attrs):
    m = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[name] = m
    return m


class _Obj:
    """Swallows arbitrary attributes — for things that only hold state."""

    def __init__(self, **kw):
        self.__dict__.update(kw)


# ============================ Clock ============================
# CircuitPython: time.time() follows the RTC, which starts at 2000-01-01.
_rtc_offset = 946684800 - _real_time()


def _device_time():
    return _real_time() + _rtc_offset


class _RTC:
    @property
    def datetime(self):
        return time.localtime(_device_time())

    @datetime.setter
    def datetime(self, st):
        global _rtc_offset
        _rtc_offset = time.mktime(st) - _real_time()


def set_rtc(epoch):
    global _rtc_offset
    _rtc_offset = epoch - _real_time()


# ============================ Display / LED ============================
class Label:
    def __init__(self, font=None, text="", color=0, x=0, y=0, **kw):
        self.text, self.x, self.y = text, x, y


class Group(list):
    def __init__(self, **kw):
        super().__init__()


class _Pixel(list):
    def __init__(self, *a, **kw):
        super().__init__([(0, 0, 0)])

    def show(self):
        _state["led"] = self[0]


# ============================ I2C ============================
# Status bytes of the displays: SSD1327 measured on the device (0x02),
# SSD1306 as documented (0x43 = display off, ID 0x03).
DISPLAY_STATUS = {"ssd1306": 0x43, "ssd1327": 0x02, "unknown": 0x5A}


class _I2C:
    def __init__(self):
        self._locked = False

    def try_lock(self):
        if self._locked:
            return False
        self._locked = True
        return True

    def unlock(self):
        self._locked = False

    def scan(self):
        return [] if _state["display_kind"] == "none" else [_state["display_addr"]]

    def readfrom_into(self, addr, buf):
        if not self._locked:
            raise RuntimeError("Function requires lock")
        if addr not in self.scan():
            raise OSError(errno.EIO, "Input/output error")
        for n in range(len(buf)):
            buf[n] = DISPLAY_STATUS[_state["display_kind"]]


_i2c = None


def _stemma_i2c():
    global _i2c                  # board.STEMMA_I2C() is a singleton on the device
    if _i2c is None:
        _i2c = _I2C()
    return _i2c


# ============================ Pins ============================
_claimed = {}


def _claim(pin):
    name = getattr(pin, "name", None)
    if name is None:
        raise TypeError(f"not a pin: {pin!r}")
    if name in _claimed:
        raise ValueError(f"{name} in use")
    _claimed[name] = True
    return name


class _DigitalInOut:
    def __init__(self, pin):
        self._name = _claim(pin)
        self.direction = None
        self.pull = None

    @property
    def value(self):
        return True            # A0 jumper open = normal operation

    def deinit(self):
        _claimed.pop(self._name, None)


# ============================ SD card ============================
def _sdcard(spi, cs):
    if not isinstance(cs, _DigitalInOut):
        raise TypeError("adafruit_sdcard.SDCard expects a digitalio.DigitalInOut")
    if not _state["sd_present"]:
        raise OSError(errno.ENODEV, "no SD card")
    return _Obj()


def _mount(vfs, path):
    fs.sd_mounted = True


def _umount(path):
    if not fs.sd_mounted:
        raise OSError(errno.EINVAL, "not mounted")
    fs.sd_mounted = False


# ============================ Wi-Fi / HTTP ============================
class _Radio:
    def __init__(self):
        self.connected = False
        self.ipv4_address = None
        self._ap_since = None

    @property
    def ipv4_address_ap(self):
        # As on the ESP32-S3: the AP address appears a moment after start_ap()
        if self._ap_since is None or time.monotonic() - self._ap_since < 1.0:
            return None
        return "192.168.4.1"

    def connect(self, ssid, password, timeout=None, **kw):
        if _state["wifi_off"]:
            time.sleep(2)
            raise ConnectionError("No network with that ssid")
        self.connected = True
        self.ipv4_address = "192.168.33.2"

    def start_ap(self, ssid=None, password=None, **kw):
        if password is not None and not 8 <= len(password) <= 63:
            raise ValueError("password length must be 8-63")
        self._ap_since = time.monotonic()

    def stop_ap(self):
        self._ap_since = None


class _Response:
    open_count = 0

    def __init__(self, raw, status_code):
        self._raw = raw
        self.status_code = status_code
        self._closed = False
        _Response.open_count += 1

    def json(self):
        import json
        return json.loads(self._raw)

    def close(self):
        if not self._closed:
            self._closed = True
            _Response.open_count -= 1

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


class _Session:
    def __init__(self, pool=None, ssl_context=None):
        pass

    def get(self, url, timeout=None, **kw):
        # Every request to the Shelly is recorded — the tests check the 5 s rule
        method = url.split("/rpc/", 1)[-1].split("?")[0]
        _state["shelly_requests"].append((time.monotonic(), method))
        del _state["shelly_requests"][:-200]
        if not _state["radio"].connected:
            raise OSError(errno.EHOSTUNREACH, "no route")
        if _state["shelly_offline"]:
            time.sleep(timeout or 3)          # blocks like the real socket
            raise OSError(errno.ETIMEDOUT, "ETIMEDOUT")
        url = url.replace(f"http://{_state['shelly_addr']}", f"http://127.0.0.1:{_state['shelly_port']}")
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return _Response(r.read(), r.status)
        except urllib.error.HTTPError as e:
            return _Response(e.read(), e.code)
        except urllib.error.URLError as e:
            raise OSError(f"Shelly unreachable: {e}") from e


# ============================ Microcontroller ============================
class _NVM:
    def __init__(self, path):
        self._path = path
        try:
            with open(path, "rb") as f:
                self._buf = bytearray(f.read().ljust(32, b"\x00"))
        except OSError:
            self._buf = bytearray(32)

    def __getitem__(self, i):
        return self._buf[i]

    def __setitem__(self, i, v):
        self._buf[i] = v & 0xFF
        with open(self._path, "wb") as f:
            f.write(self._buf)


class _Watchdog:
    """Records when the program would have been reset by the watchdog."""

    def __init__(self):
        self.timeout = 0
        self.mode = None
        self._fed = time.monotonic()
        threading.Thread(target=self._watch, daemon=True).start()

    def feed(self):
        self._fed = time.monotonic()

    def _watch(self):
        while True:
            time.sleep(1)
            if self.mode and self.timeout and time.monotonic() - self._fed > self.timeout:
                _state["watchdog_trips"] += 1
                print("[SIM] WATCHDOG would reset the device now")
                self._fed = time.monotonic()


def _reset():
    import os
    print("[SIM] microcontroller.reset() -> simulator restarts")
    sys.stdout.flush()
    os.environ["ENERGY_LOGGER_SIM_RESET"] = "1"
    os.execv(sys.executable, [sys.executable] + sys.argv)


# ============================ Install ============================
def install(state, nvm_path, secrets, config):
    global _state
    _state = state
    state.setdefault("watchdog_trips", 0)
    state.setdefault("shelly_requests", [])
    state["open_responses"] = lambda: _Response.open_count

    pins = {n: _Obj(name=n) for n in ("A0", "A1", "A2", "A3", "SCK", "MOSI", "MISO",
                                      "NEOPIXEL", "SDA", "SCL")}
    _mod("board", SPI=lambda: _Obj(), STEMMA_I2C=_stemma_i2c, **pins)
    _mod("digitalio", DigitalInOut=_DigitalInOut,
         Direction=_Obj(INPUT="in", OUTPUT="out"), Pull=_Obj(UP="up", DOWN="down"))
    _mod("storage", VfsFat=lambda card: _Obj(), mount=_mount, umount=_umount,
         remount=lambda *a, **k: None)
    _mod("adafruit_sdcard", SDCard=_sdcard)
    _mod("rtc", RTC=_RTC)
    time.time = _device_time

    _mod("displayio", Group=Group, release_displays=lambda: None)
    _mod("terminalio", FONT=_Obj())
    def _bus(i2c, device_address=0):
        if i2c._locked:
            raise RuntimeError("I2C bus still locked")   # detection must unlock
        return _Obj(address=device_address)

    _mod("i2cdisplaybus", I2CDisplayBus=_bus)

    def _display(kind):
        def make(bus, width=128, height=64):
            d = _Obj(root_group=None, kind=kind, width=width, height=height)
            state["display"] = d
            return d
        return make

    _mod("adafruit_displayio_ssd1306", SSD1306=_display("ssd1306"))
    _mod("adafruit_ssd1327", SSD1327=_display("ssd1327"))
    pkg = _mod("adafruit_display_text")
    pkg.label = _mod("adafruit_display_text.label", Label=Label)
    _mod("neopixel", NeoPixel=_Pixel)

    state["radio"] = _Radio()
    _mod("wifi", radio=state["radio"])
    _mod("socketpool", SocketPool=lambda radio=None: _Obj())
    _mod("adafruit_requests", Session=_Session)
    _mod("adafruit_httpserver",
         Server=httpserver.Server, Request=httpserver.Request,
         Response=httpserver.Response, FileResponse=httpserver.FileResponse,
         ChunkedResponse=httpserver.ChunkedResponse,
         ServerStoppedError=httpserver.ServerStoppedError)

    _mod("watchdog", WatchDogMode=_Obj(RESET="RESET", RAISE="RAISE"))
    _mod("microcontroller", nvm=_NVM(nvm_path), reset=_reset,
         cpu=_Obj(reset_reason=state.get("reset_reason", "POWER_ON"), temperature=42.5),
         watchdog=_Watchdog())

    # secrets.py: the stdlib has a module of that name — replace it
    _mod("secrets", secrets=secrets)
    _mod("config", config=config)

    import gc
    gc.mem_free = lambda: 140_000
