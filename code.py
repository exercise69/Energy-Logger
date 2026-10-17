# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Uwe Piro
# https://github.com/exercise69/Energy-Logger

# ================= ENERGY-LOGGER — QT Py ESP32-S3 + Shelly Plus Plug S =========
#
# Reads power and energy from the Shelly (joining the Shelly's own Wi-Fi in
# station mode), logs them to the SD card and shows them on the OLED and in a
# PWA served over HTTPS on the logger's own access point.

# ── Software version ────────────────────────────────────────────
# Set by tools/stamp.py, not by hand — the script keeps these lines, app.js
# and the service worker cache name in sync.
EL_VERSION = "2.0"
EL_BUILD   = 21
EL_DATE    = "2026-10-17"
EL_NOTE    = "A0 write-protect jumper and boot.py removed"

import time, board, digitalio, storage, rtc, os, json, gc, asyncio
import microcontroller, wifi, socketpool
import adafruit_sdcard
import adafruit_requests
from adafruit_httpserver import (Server, Request, Response, FileResponse,
                                 ChunkedResponse, ServerStoppedError)
from secrets import secrets
from config import config

# Short durations use monotonic_ns(): monotonic() is a float and loses
# millisecond resolution after a bit more than an hour of uptime.
try:
    _mono_ns = time.monotonic_ns
except AttributeError:
    def _mono_ns():
        return int(time.monotonic() * 1000000000)

# ================= STATE =================
class Intermediate:
    def __init__(self):
        # Shelly readings
        self.power = 0.0
        self.energy = 0.0
        self.output = False
        self.voltage = None
        self.current = None
        self.shelly_temp = None
        self.shelly_state = "starting"    # starting | searching | ok | offline
        self.shelly_ok = False
        self.shelly_last_ok = None        # monotonic time of the last good poll
        self.shelly_has_time = False
        self.time_to_shelly_mono = -3600.0
        self.commands = []                # jobs for the Shelly, see task_shelly
        # Network
        self.ap_ip = None
        self.sta_ip = None
        # Clock
        self.rtc_synced = False
        self.time_source = ""             # phone | manual | shelly
        self.time_set_mono = 0.0
        # SD card and data log
        self.logging_enabled = config.get("logging_enabled", True)
        self.sd_status = "unmounted"      # unmounted | ok | error
        self.sd_writing = "idle"          # idle | writing | ok | error | retry | off
        self.sd_queue_len = 0
        self.sd_queue_dropped = 0
        self.sd_header_ok = False
        self.sd_error_txt = ""
        self.sd_error_at = ""
        self.sd_error_count = 0
        # Diagnostics, per health-log window
        self.loop_dt = 0.0
        self.loop_dt_max = 0.0
        self.blocked_at = ""
        self.shelly_max_s = 0.0
        self.shelly_errors = 0
        self.sd_max_s = 0.0
        self.srv_errors = 0
        self.srv_error_txt = ""
        self.cpu_temp = 0.0
        self.mem_free = 0
        self.mem_block = 0
        self.display_test_until = 0.0

intermediate = Intermediate()

# ================= DISPLAY =================
# A missing display or a stuck I2C bus must not stop the logger — measuring
# and logging matter more than the display.
#
# Two displays are in use on the same address 0x3D: SSD1306 128x64 and
# SSD1327 128x128. They are told apart by the status byte an I2C read returns:
#   SSD1327: 0x02                    (measured on the device, 2026-10-12)
#   SSD1306: low nibble 0x03/0x06/0x07, e.g. 0x03 or 0x43 (datasheet/common
#            drivers — not yet measured on our hardware)
# config["display"] can force a type if the detection is ever wrong.
DISPLAY_SIZES = {"ssd1306": (128, 64), "ssd1327": (128, 128)}
DISPLAY_ADDRESSES = (0x3D, 0x3C)

def classify_display(status):
    """Display type for an I2C status byte, or None if unknown."""
    if status is None:
        return None
    if status & 0x3F == 0x02:
        return "ssd1327"
    if status & 0x0F in (0x03, 0x06, 0x07):
        return "ssd1306"
    return None

def detect_display(i2c):
    """Scan the bus. Returns (address, status byte) or (None, None)."""
    while not i2c.try_lock():
        pass
    try:
        found = i2c.scan()
        wanted = config.get("display_address", "auto")
        for addr in (DISPLAY_ADDRESSES if wanted == "auto" else (wanted,)):
            if addr in found:
                buf = bytearray(1)
                try:
                    i2c.readfrom_into(addr, buf)
                    return addr, buf[0]
                except OSError:
                    return addr, None
        return None, None
    finally:
        i2c.unlock()

# Result of the detection, for status.json and the BOOT line
display_info = {"type": "none", "address": None, "status": None, "how": ""}
_lines = []
try:
    import displayio, terminalio
    from i2cdisplaybus import I2CDisplayBus
    from adafruit_display_text import label
    displayio.release_displays()
    _i2c = board.STEMMA_I2C()
    _addr, _status = detect_display(_i2c)
    _forced = config.get("display", "auto")
    if _addr is None:
        _kind, _how = "none", "nothing on 0x3C/0x3D"
    elif _forced != "auto":
        _kind, _how = _forced, "config"
    else:
        _kind = classify_display(_status)
        _how = "auto"
        if _kind is None:
            # Unknown status byte: the original hardware's display is the safe guess
            _kind, _how = "ssd1306", "fallback"
    display_info.update(type=_kind, address=_addr, status=_status, how=_how)

    if _kind in DISPLAY_SIZES:
        _w, _h = DISPLAY_SIZES[_kind]
        _display_bus = I2CDisplayBus(_i2c, device_address=_addr)
        if _kind == "ssd1327":
            import adafruit_ssd1327
            display = adafruit_ssd1327.SSD1327(_display_bus, width=_w, height=_h)
        else:
            import adafruit_displayio_ssd1306
            display = adafruit_displayio_ssd1306.SSD1306(_display_bus, width=_w, height=_h)
        _group = displayio.Group()
        display.root_group = _group
        # Six lines spread over the height: 11 px apart on 64, 21 px on 128
        _step = (_h - 9) // 5
        for _i in range(6):
            _lbl = label.Label(terminalio.FONT, text="", color=0xFFFFFF,
                               x=0, y=5 + _i * _step)
            _group.append(_lbl)
            _lines.append(_lbl)
    status_txt = "-" if _status is None else hex(_status)
    print(f"[DISPLAY] {_kind} at {_addr and hex(_addr)} (status {status_txt}, {_how})")
except Exception as e:
    display_info.update(type="error", how=str(e))
    print("[DISPLAY] not available:", e)

def show_line(n, text):
    """Only touch a label when its text changes — every assignment rebuilds
    the glyphs and allocates memory."""
    if n < len(_lines) and _lines[n].text != text:
        _lines[n].text = text

# ================= LED =================
try:
    import neopixel
    _pixel = neopixel.NeoPixel(board.NEOPIXEL, 1, brightness=0.1, auto_write=False)
except Exception:
    _pixel = None

COLOR_OK  = (0, 50, 0)
COLOR_ERR = (50, 0, 0)
COLOR_OFF = (0, 0, 0)
_led = None

def set_led(color):
    global _led
    if _pixel is not None and color != _led:
        _pixel[0] = color
        _pixel.show()
        _led = color

# ================= CLOCK =================
# The Shelly AP has no internet, so NTP never works. The time comes from the
# phone (the app sends it on opening while the clock is unset), from manual
# entry, or from the Shelly if it has a time itself.
# The RTC runs on Central European local time.

def _cet_offset_hours(utc_epoch):
    """Offset for Central Europe: 1 = CET (winter), 2 = CEST (summer).

    EU rule: summer time from the last Sunday in March 01:00 UTC to the last
    Sunday in October 01:00 UTC. Computed here because CircuitPython has no
    time zone database.
    """
    t = time.localtime(utc_epoch)   # no time zone → equals UTC
    m, d, hh = t.tm_mon, t.tm_mday, t.tm_hour
    if m < 3 or m > 10:
        return 1
    if 3 < m < 10:
        return 2
    # March/October: find the date of the last Sunday.
    # 1970-01-01 was a Thursday; +4 shifts Sunday to 0.
    days_since_sunday = ((utc_epoch // 86400) + 4) % 7
    last_sunday       = d - days_since_sunday
    # The last Sunday of a 31-day month always falls on the 25th–31st.
    switched = last_sunday >= 25 and not (last_sunday == d and hh < 1)
    if m == 3:
        return 2 if switched else 1
    return 1 if switched else 2

def set_clock(utc_epoch, source):
    utc_epoch = int(utc_epoch)
    rtc.RTC().datetime = time.localtime(utc_epoch + _cet_offset_hours(utc_epoch) * 3600)
    intermediate.rtc_synced = True
    intermediate.time_source = source
    intermediate.time_set_mono = time.monotonic()
    print(f"[CLOCK] set from {source}: {timestamp()}")

def local_to_utc(local_epoch):
    """Within the hour of a DST switch this can be one hour off — good
    enough for the Shelly and for manual entry."""
    return local_epoch - _cet_offset_hours(local_epoch - 3600) * 3600

def timestamp():
    """YYYY-MM-DD hh:mm:ss — or the uptime while the clock is unset."""
    if not intermediate.rtc_synced:
        return f"T+{time.monotonic():.0f}s"
    t = rtc.RTC().datetime
    return (f"{t.tm_year}-{t.tm_mon:02d}-{t.tm_mday:02d} "
            f"{t.tm_hour:02d}:{t.tm_min:02d}:{t.tm_sec:02d}")

# ================= SD CARD =================
SD_PATH          = "/sd"
CSV_FILE         = "energy_log.csv"
CSV_MONTH_PREFIX = "energy_log_"          # energy_log_2026-10.csv
CSV_HEADER       = "time,power_w,energy_wh,output\n"
ERROR_LOG_FILE   = "error_log.txt"
ERROR_LOG_OLD    = "error_log.1.txt"
MAX_ERROR_LOG    = 32768                  # then rotate one generation
HEALTH_LOG_FILE  = "health_log.csv"
MAX_HEALTH_LOG   = 98304                  # 96 KB ~ 4 days at 5 minutes
HEALTH_HEADER    = ("time,free_b,block_b,cpu_c,loop_s,loop_max_s,blocked_at,"
                    "shelly_max_s,shelly_errors,sd_max_s,srv_errors,"
                    "status_requests,uptime_h,sd\n")
MAX_QUEUE        = 100

# NVM bytes survive every reset
NVM_IDX_FLAG     = 0     # 0xAB = booted but not yet 60 s healthy
NVM_IDX_CRASHES  = 1     # crash counter (0–255)
NVM_IDX_SAFEMODE = 2     # consecutive self-heals from safemode.py
NVM_FLAG_BOOT    = 0xAB

sd_log_queue = []
_spi     = None
_sd_card = None
_sd_cs   = None

def _sd_release():
    """Release the CS pin. Without this every second mount fails with "A1 in use"."""
    global _sd_card, _sd_cs
    _sd_card = None
    if _sd_cs is not None:
        try: _sd_cs.deinit()
        except Exception: pass
        _sd_cs = None

def _sd_error(where, e):
    """Remember an SD error. Only the change from ok to error goes into the
    error log — the log lives on the card itself."""
    was_ok = intermediate.sd_status == "ok"
    intermediate.sd_error_txt = f"{where}: {e}"
    intermediate.sd_error_at = timestamp()
    intermediate.sd_error_count += 1
    if was_ok:
        log_error(f"SD ERROR {intermediate.sd_error_txt}")

def mount_sd():
    # adafruit_sdcard, not sdcardio: on the SolarLoader sdcardio caused write
    # errors and duplicate lines in the field (09/2026).
    global _spi, _sd_card, _sd_cs
    try:
        storage.umount(SD_PATH)
    except Exception:
        pass
    _sd_release()
    try:
        # The SPI bus is created once. It used to be created on every mount —
        # from the second attempt on that failed with "SCK in use", so the
        # automatic remount could never succeed.
        if _spi is None:
            _spi = board.SPI()
        _sd_cs = digitalio.DigitalInOut(getattr(board, config.get("sd_cs_pin", "A1")))
        _sd_card = adafruit_sdcard.SDCard(_spi, _sd_cs)
        storage.mount(storage.VfsFat(_sd_card), SD_PATH)
    except Exception as e:
        print("[SD] mount failed:", e)
        if "Mount point" in str(e):
            # CircuitPython 10 needs an empty folder "sd" on CIRCUITPY. code.py
            # cannot create it (CIRCUITPY is read-only for code.py).
            e = "folder 'sd' missing on CIRCUITPY — create it from the computer"
            print("[SD]", e)
        _sd_error("mount", e)
        intermediate.sd_status = "error"
        _sd_release()
        return False
    intermediate.sd_status = "ok"
    intermediate.sd_header_ok = False
    print("[SD] mounted")
    return True

def log_error(msg):
    print(f"[ERR] {msg}")
    try:
        path = f"{SD_PATH}/{ERROR_LOG_FILE}"
        try:
            too_big = os.stat(path)[6] > MAX_ERROR_LOG
        except OSError:
            too_big = False
        if too_big:
            # Rotate instead of delete, otherwise a chatty condition wipes
            # the trace of a crash.
            try:
                try: os.remove(f"{SD_PATH}/{ERROR_LOG_OLD}")
                except OSError: pass
                os.rename(path, f"{SD_PATH}/{ERROR_LOG_OLD}")
            except Exception as e:
                print(f"[ERR] rotation failed ({e}) — clearing log")
                try: os.remove(path)
                except OSError: pass
        with open(path, "a") as f:
            f.write(f"{timestamp()}  {msg}\n")
    except Exception:
        pass

def enqueue_log():
    if not intermediate.logging_enabled:
        return
    sd_log_queue.append(f"{timestamp()},{intermediate.power:.1f},"
                        f"{intermediate.energy:.1f},{int(intermediate.output)}\n")
    if len(sd_log_queue) > MAX_QUEUE:
        drop = len(sd_log_queue) - MAX_QUEUE
        del sd_log_queue[:drop]
        intermediate.sd_queue_dropped += drop
    intermediate.sd_queue_len = len(sd_log_queue)

_log_month = None   # YYYY-MM of the lines in energy_log.csv, None = not known yet

def _is_month(s):
    # "2026-10" — lines written before the clock was set start with "T+123s"
    return len(s) == 7 and s[:2] == "20" and s[4] == "-"

def _check_month(csv_path, csv_line):
    """On a month change, move energy_log.csv aside and start a new file.

    The month comes from the line's own timestamp, not from the clock. On the
    first call after boot the month of the first dated line is read — the file
    may be left over from the previous month.
    """
    global _log_month
    month = csv_line[:7]
    if not _is_month(month):
        return
    if _log_month is None:
        _log_month = month
        try:
            with open(csv_path, "r") as f:
                f.readline()                       # header
                for _ in range(50):
                    line = f.readline()
                    if not line:
                        break
                    if _is_month(line[:7]):
                        _log_month = line[:7]
                        break
        except OSError:
            pass
    if _log_month == month:
        return
    old = f"{SD_PATH}/{CSV_MONTH_PREFIX}{_log_month}.csv"
    n = 2
    while True:                                    # never overwrite
        try:
            os.stat(old)
        except OSError:
            break
        old = f"{SD_PATH}/{CSV_MONTH_PREFIX}{_log_month}_{n}.csv"
        n += 1
    try:
        os.rename(csv_path, old)
        intermediate.sd_header_ok = False
        log_error(f"DATA LOG rotated: {CSV_FILE} -> {old.split('/')[-1]}")
    except Exception as e:
        # Better keep writing to the old file than lose lines
        print(f"[SD] rotation failed: {e}")
        return
    _log_month = month

async def task_sd_writer():
    RETRY_DELAY = 5
    while True:
        if not intermediate.logging_enabled:
            intermediate.sd_writing = "off"
            await asyncio.sleep(0.5)
            continue
        if not sd_log_queue:
            intermediate.sd_writing = "idle"
            await asyncio.sleep(0.5)
            continue

        # Remount after every error. "error" used to stick until somebody
        # restarted the device.
        if intermediate.sd_status != "ok":
            intermediate.sd_writing = "retry"
            if not mount_sd():
                await asyncio.sleep(RETRY_DELAY)
                continue

        intermediate.sd_writing = "writing"
        csv_path = f"{SD_PATH}/{CSV_FILE}"
        csv_line = sd_log_queue[0]
        size_before = 1 << 30            # unknown: never count as written
        try:
            _check_month(csv_path, csv_line)
            if not intermediate.sd_header_ok:
                try:
                    new_file = os.stat(csv_path)[6] == 0
                except OSError:
                    new_file = True
                if new_file:
                    with open(csv_path, "w") as f:
                        f.write(CSV_HEADER)
                intermediate.sd_header_ok = True
            # Remember the size: if the driver reports an error although the
            # line is already on the card, it must not be written twice.
            try:
                size_before = os.stat(csv_path)[6]
            except OSError:
                size_before = 0
            t0 = _mono_ns()
            with open(csv_path, "a") as f:
                f.write(csv_line)
            dt = (_mono_ns() - t0) / 1000000000.0
            if dt > intermediate.sd_max_s:
                intermediate.sd_max_s = dt
            sd_log_queue.pop(0)
            intermediate.sd_queue_len = len(sd_log_queue)
            intermediate.sd_writing = "ok"
        except Exception as e:
            print("[SD] write error:", e)
            _sd_error(f"writing {CSV_FILE}", e)
            intermediate.sd_status = "error"
            intermediate.sd_writing = "error"
            try:
                if (sd_log_queue and
                        os.stat(csv_path)[6] >= size_before + len(csv_line.encode())):
                    sd_log_queue.pop(0)          # already on the card
                    intermediate.sd_queue_len = len(sd_log_queue)
            except Exception:
                pass
            await asyncio.sleep(RETRY_DELAY)
            continue
        await asyncio.sleep(0.05)

# ================= HEALTH LOG =================
_boot_mono = time.monotonic()
_status_requests = 0
_health_header_checked = False

def _largest_block():
    """Largest allocatable contiguous block. gc.mem_free() only reports the
    sum — a TLS handshake fails on fragmentation, not on the total."""
    for size in (32768, 16384, 8192, 4096, 2048, 1024):
        try:
            _probe = bytearray(size)
            del _probe
            return size
        except MemoryError:
            continue
    return 0

def log_health(free, block, uptime_h):
    global _health_header_checked
    try:
        path = f"{SD_PATH}/{HEALTH_LOG_FILE}"
        new_file = True
        try:
            size = os.stat(path)[6]
            new_file = size == 0
            if size > MAX_HEALTH_LOG:
                os.remove(path)
                new_file = True
        except OSError:
            pass
        # If columns were added, the old file no longer matches the header.
        if not new_file and not _health_header_checked:
            with open(path, "r") as f:
                if f.readline() != HEALTH_HEADER:
                    os.remove(path)
                    new_file = True
        _health_header_checked = True
        i = intermediate
        with open(path, "a") as f:
            if new_file:
                f.write(HEALTH_HEADER)
            f.write(f"{timestamp()},{free},{block},{i.cpu_temp:.1f},"
                    f"{i.loop_dt:.2f},{i.loop_dt_max:.2f},{i.blocked_at},"
                    f"{i.shelly_max_s:.2f},{i.shelly_errors},{i.sd_max_s:.3f},"
                    f"{i.srv_errors},{_status_requests},{uptime_h:.1f},{i.sd_status}\n")
    except Exception as e:
        print(f"[HEALTH] write error: {e}")

async def task_health():
    """Clean up every minute, write one line of operating state every
    health_interval seconds. A hard crash gives no warning as an error —
    without this trace nothing would be logged before an outage."""
    interval = config.get("health_interval", 300)
    next_line = time.monotonic() + interval
    while True:
        await asyncio.sleep(60)
        gc.collect()
        free = gc.mem_free()
        if free < 20000:
            log_error(f"LOW RAM: {free} bytes free after GC")
        if time.monotonic() < next_line:
            continue
        next_line = time.monotonic() + interval

        i = intermediate
        block = _largest_block()
        try:
            i.cpu_temp = microcontroller.cpu.temperature
        except Exception:
            i.cpu_temp = 0.0
        uptime_h = (time.monotonic() - _boot_mono) / 3600.0
        i.mem_free, i.mem_block = free, block
        log_health(free, block, uptime_h)

        if block < 8192:
            log_error(f"MEMORY FRAGMENTED  largest block {block}B with {free}B free")
        if i.loop_dt_max > 6.0:
            log_error(f"SLOW LOOP  {i.loop_dt_max:.1f}s at {i.blocked_at}  "
                      f"(Shelly max {i.shelly_max_s:.1f}s, SD max {i.sd_max_s:.3f}s)")
        if i.srv_errors:
            log_error(f"SERVER ERRORS  {i.srv_errors} in {interval}s  "
                      f"(last: {i.srv_error_txt})")

        # Close the window
        i.loop_dt_max = 0.0
        i.blocked_at = ""
        i.shelly_max_s = 0.0
        i.shelly_errors = 0
        i.sd_max_s = 0.0
        i.srv_errors = 0

async def task_healthy():
    """After 60 s of running, the boot counts as successful."""
    await asyncio.sleep(60)
    try:
        microcontroller.nvm[NVM_IDX_FLAG] = 0x00
        microcontroller.nvm[NVM_IDX_SAFEMODE] = 0   # safemode.py starts counting again
    except Exception:
        pass
    print("[BOOT] healthy after 60 s")

def _log_boot():
    """Every boot goes into the error log, a detected crash with its trace."""
    try:
        reason = str(microcontroller.cpu.reset_reason)
    except Exception:
        reason = "unknown"
    try:
        nvm = microcontroller.nvm
        expected = "POWER_ON" in reason or "RESET_PIN" in reason
        if nvm[NVM_IDX_FLAG] == NVM_FLAG_BOOT and not expected:
            nvm[NVM_IDX_CRASHES] = min(nvm[NVM_IDX_CRASHES] + 1, 255)
            log_error(f"CRASH DETECTED  reset={reason}  crashes={nvm[NVM_IDX_CRASHES]}")
            try:
                with open("/boot_out.txt", "r") as f:
                    log_error("boot_out.txt:\n" + f.read())
            except Exception:
                pass
        d = display_info
        log_error(f"BOOT  v{EL_VERSION} b{EL_BUILD}  reset={reason}  "
                  f"crashes={nvm[NVM_IDX_CRASHES]}  selfheal={nvm[NVM_IDX_SAFEMODE]}  "
                  f"display={d['type']}@{d['address'] and hex(d['address'])}"
                  f"/{d['status'] if d['status'] is None else hex(d['status'])}/{d['how']}")
        nvm[NVM_IDX_FLAG] = NVM_FLAG_BOOT
    except Exception as e:
        print("[BOOT] NVM error:", e)

# ================= SHELLY =================
SHELLY_SSID     = secrets["shelly_ap_ssid"]
SHELLY_PASSWORD = secrets["shelly_ap_password"]
SHELLY_BASE     = f"http://{config['shelly_ip']}/rpc/"
# Polling faster than every 5 s causes trouble on the Shelly — this holds even
# if config.py says less, and for the poll right after a switch command.
POLL_INTERVAL   = max(5, config.get("poll_interval", 10))
POLL_MIN_GAP    = 5      # a status poll never follows any request faster than this
COMMAND_MIN_GAP = 1      # commands (toggle, time) keep at least this distance
SHELLY_TIMEOUT  = 3      # seconds; on its own AP the Shelly answers in milliseconds
SHELLY_TIME_RESYNC = 6 * 3600

pool     = socketpool.SocketPool(wifi.radio)     # the only pool in the program
_session = adafruit_requests.Session(pool)       # the Shelly speaks plain HTTP
_last_request = -60.0

def _wifi_ok():
    """Connected AND with an address — on the SolarLoader `connected` alone
    reported 0.0.0.0 as fine."""
    if not wifi.radio.connected:
        return False
    ip = wifi.radio.ipv4_address
    return ip is not None and str(ip) != "0.0.0.0"

def _shelly_rpc(method):
    """One RPC call. The response is always closed — previously every poll
    left a socket open until none were left."""
    global _last_request
    _last_request = time.monotonic()
    t0 = _mono_ns()
    try:
        with _session.get(SHELLY_BASE + method, timeout=SHELLY_TIMEOUT) as r:
            if r.status_code != 200:
                raise OSError(f"HTTP {r.status_code}")
            return r.json()
    finally:
        dt = (_mono_ns() - t0) / 1000000000.0
        if dt > intermediate.shelly_max_s:
            intermediate.shelly_max_s = dt

async def _connect_to_shelly():
    delay = 5
    while not _wifi_ok():
        intermediate.sta_ip = None
        intermediate.shelly_state = "searching"
        try:
            wifi.radio.connect(SHELLY_SSID, SHELLY_PASSWORD, timeout=10)
        except Exception as e:
            print(f"[WIFI] {SHELLY_SSID}: {e}")
        if _wifi_ok():
            break
        await asyncio.sleep(delay)
        delay = min(delay * 2, 60)
    intermediate.sta_ip = str(wifi.radio.ipv4_address)
    log_error(f"SHELLY WIFI connected  ip={intermediate.sta_ip}")

def _poll_shelly():
    i = intermediate
    try:
        d = _shelly_rpc("Shelly.GetStatus")
    except Exception as e:
        i.shelly_errors += 1
        if i.shelly_ok:
            log_error(f"SHELLY unreachable: {e}")
        i.shelly_ok = False
        i.shelly_state = "offline"
        set_led(COLOR_ERR)
        return False

    s0 = d.get("switch:0") or {}
    i.power = float(s0.get("apower") or 0.0)
    i.energy = float((s0.get("aenergy") or {}).get("total") or 0.0)
    i.output = bool(s0.get("output", False))
    i.voltage = s0.get("voltage")
    i.current = s0.get("current")
    i.shelly_temp = (s0.get("temperature") or {}).get("tC")
    if not i.shelly_ok and i.shelly_last_ok is not None:
        log_error("SHELLY reachable again")
    i.shelly_ok = True
    i.shelly_last_ok = time.monotonic()
    i.shelly_state = "ok"
    set_led(COLOR_OK)

    # unixtime is UTC and null while the Shelly has no time itself.
    # (utc_offset is in seconds; the old code multiplied it by 3600 again.)
    unixtime = (d.get("sys") or {}).get("unixtime")
    i.shelly_has_time = bool(unixtime)
    if unixtime:
        if not i.rtc_synced or (i.time_source == "shelly" and
                time.monotonic() - i.time_set_mono > SHELLY_TIME_RESYNC):
            set_clock(unixtime, "shelly")
    elif (i.rtc_synced and "time_to_shelly" not in i.commands and
            time.monotonic() - i.time_to_shelly_mono > 3600):
        # At most once an hour — if the Shelly does not take the time, it
        # should not get a command after every poll.
        i.commands.append("time_to_shelly")

    enqueue_log()
    return True

def _run_command(cmd):
    i = intermediate
    try:
        if cmd == "toggle":
            # The reply tells the previous state — no extra poll needed
            d = _shelly_rpc("Switch.Toggle?id=0")
            i.output = not d.get("was_on", i.output)
        elif cmd == "time_to_shelly":
            i.time_to_shelly_mono = time.monotonic()
            _shelly_rpc(f"Sys.SetTime?unixtime={int(local_to_utc(time.time()))}")
            print("[CLOCK] time sent to the Shelly")
    except Exception as e:
        log_error(f"SHELLY COMMAND {cmd} failed: {e}")

async def task_shelly():
    """The only place that talks to the Shelly. The web UI and the clock put
    jobs into intermediate.commands; so two requests never share the session
    at the same time, and no web request waits for the Shelly."""
    i = intermediate
    next_poll = 0.0
    while True:
        if not _wifi_ok():
            if i.sta_ip is not None:
                log_error("SHELLY WIFI lost")
            i.shelly_ok = False
            set_led(COLOR_ERR)
            await _connect_to_shelly()
            next_poll = 0.0

        now = time.monotonic()
        if i.commands:
            if now - _last_request >= COMMAND_MIN_GAP:
                _run_command(i.commands.pop(0))
        elif now >= next_poll and now - _last_request >= POLL_MIN_GAP:
            ok = _poll_shelly()
            next_poll = time.monotonic() + (POLL_INTERVAL if ok else POLL_MIN_GAP)
        await asyncio.sleep(0.2)

# ================= WEB SERVER =================
AP_SSID     = secrets.get("ap_ssid", "Energy-Logger")
AP_PASSWORD = secrets["ap_password"]      # deliberately without a default

def _exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False

# HTTPS is required for the PWA on iOS. Without a certificate the server still
# runs — plain HTTP on port 80, with an entry in the error log.
HTTPS = _exists("/server.crt") and _exists("/server.key")
server = Server(pool, root_path="/html", https=HTTPS,
                certfile="server.crt", keyfile="server.key", debug=False)

def start_server():
    try:
        server.stop()
    except Exception:
        pass
    # All interfaces, not the AP address: on the device that address was
    # briefly None after start_ap(), and the server then refused to start.
    server.start("0.0.0.0", 443 if HTTPS else 80)

def ap_address():
    ip = wifi.radio.ipv4_address_ap
    return None if ip is None else str(ip)

def _json(request, data, status=200):
    return Response(request, json.dumps(data), content_type="application/json",
                    status=status)

@server.route("/")
def route_index(request: Request):
    return FileResponse(request, "index.html", root_path="/html")

@server.route("/ping")
def route_ping(request: Request):
    return Response(request, "pong")

@server.route("/status.json")
def route_status(request: Request):
    global _status_requests
    _status_requests += 1
    i = intermediate
    try:
        log_size = os.stat(f"{SD_PATH}/{CSV_FILE}")[6]
    except OSError:
        log_size = 0
    try:
        crashes = microcontroller.nvm[NVM_IDX_CRASHES]
    except Exception:
        crashes = 0
    return _json(request, {
        "version": EL_VERSION, "build": EL_BUILD, "date": EL_DATE, "note": EL_NOTE,
        "power": i.power, "energy": i.energy, "output": i.output,
        "voltage": i.voltage, "current": i.current, "shelly_temp": i.shelly_temp,
        "shelly_state": i.shelly_state, "shelly_ok": i.shelly_ok,
        "shelly_age_s": (None if i.shelly_last_ok is None
                         else round(time.monotonic() - i.shelly_last_ok)),
        "poll_interval": POLL_INTERVAL,
        "ap_ssid": AP_SSID, "ap_ip": ap_address(), "sta_ip": i.sta_ip, "https": HTTPS,
        "rtc_synced": i.rtc_synced, "time": timestamp(), "time_source": i.time_source,
        "shelly_has_time": i.shelly_has_time,
        "logging_enabled": i.logging_enabled, "sd_status": i.sd_status,
        "sd_writing": i.sd_writing, "sd_queue_len": i.sd_queue_len,
        "sd_queue_dropped": i.sd_queue_dropped, "sd_error_txt": i.sd_error_txt,
        "sd_error_at": i.sd_error_at, "sd_error_count": i.sd_error_count,
        "sd_log_size": log_size,
        "crash_count": crashes, "mem_free": i.mem_free, "mem_block": i.mem_block,
        "cpu_temp": i.cpu_temp, "uptime_h": (time.monotonic() - _boot_mono) / 3600.0,
        "loop_dt": i.loop_dt, "loop_dt_max": i.loop_dt_max, "srv_errors": i.srv_errors,
        "status_requests": _status_requests,
        "display": display_info["type"], "display_how": display_info["how"],
        "display_address": display_info["address"],
        "display_status": display_info["status"],
    })

@server.route("/toggle_shelly", methods=["POST"])
def route_toggle_shelly(request: Request):
    # Only queue it: the Shelly task switches on its next pass (<0.2 s).
    if "toggle" not in intermediate.commands:
        intermediate.commands.append("toggle")
    return _json(request, {"ok": True})

@server.route("/toggle_logging", methods=["POST"])
def route_toggle_logging(request: Request):
    intermediate.logging_enabled = not intermediate.logging_enabled
    log_error(f"LOGGING {'on' if intermediate.logging_enabled else 'off'}")
    return _json(request, {"ok": True, "logging_enabled": intermediate.logging_enabled})

@server.route("/set_time", methods=["POST"])
def route_set_time(request: Request):
    """epoch=<UTC seconds> (app, automatic) or dt=YYYY-MM-DDThh:mm (manual, local time)."""
    form = request.form_data
    try:
        if form.get("epoch"):
            utc = int(form.get("epoch"))
            source = "phone"
        else:
            date_part, time_part = form.get("dt", "").replace("%3A", ":").split("T")
            y, m, d = (int(x) for x in date_part.split("-"))
            hh, mm = (int(x) for x in time_part.split(":")[:2])
            utc = local_to_utc(time.mktime(time.struct_time((y, m, d, hh, mm, 0, 0, -1, -1))))
            source = "manual"
        if utc < 1735689600:                       # before 2025: certainly wrong
            raise ValueError("time is before 2025")
    except Exception as e:
        return _json(request, {"ok": False, "error": str(e)}, status=400)
    set_clock(utc, source)
    if "time_to_shelly" not in intermediate.commands:
        intermediate.commands.append("time_to_shelly")
    return _json(request, {"ok": True, "time": timestamp()})

# ── Logs ────────────────────────────────────────────────────────
STREAM_CHUNK = 65536     # at most this much per request, the app fetches the rest

def _log_file(name):
    """Only energy_log.csv and its monthly files — never an arbitrary path."""
    if not name or name == CSV_FILE:
        return CSV_FILE
    if (name.startswith(CSV_MONTH_PREFIX) and name.endswith(".csv")
            and "/" not in name and ".." not in name):
        return name
    return None

@server.route("/log_files")
def route_log_files(request: Request):
    files = []
    try:
        for name in sorted(os.listdir(SD_PATH)):
            if _log_file(name) == name:
                try:
                    files.append({"file": name, "size": os.stat(f"{SD_PATH}/{name}")[6]})
                except OSError:
                    pass
    except OSError:
        pass
    return _json(request, files)

@server.route("/log_stream")
def route_log_stream(request: Request):
    """One piece of a data log file. A 10 MB file in one go would block the
    server for minutes — Shelly polling and the watchdog would stall."""
    p = request.query_params
    name = _log_file(p.get("file"))
    if name is None:
        return Response(request, "unknown file", status=400)
    path = f"{SD_PATH}/{name}"
    try:
        size = os.stat(path)[6]
        start = max(0, min(int(p.get("offset", 0)), size))
        end = min(size, start + STREAM_CHUNK, int(p.get("end", size)))
    except (OSError, ValueError):
        return Response(request, "", status=404)

    def chunks():
        with open(path, "rb") as f:
            f.seek(start)
            remaining = end - start
            while remaining > 0:
                b = f.read(min(1024, remaining))
                if not b:
                    break
                remaining -= len(b)
                try:
                    microcontroller.watchdog.feed()
                except Exception:
                    pass
                yield b

    return ChunkedResponse(request, chunks, content_type="text/plain; charset=utf-8")

def _serve_log(request, name, empty_text):
    # FileResponse streams the file in small pieces instead of reading it
    # into memory in one string.
    if not _exists(f"{SD_PATH}/{name}"):
        return Response(request, empty_text)
    return FileResponse(request, name, root_path=SD_PATH,
                        content_type="text/plain; charset=utf-8")

@server.route("/error_log")
def route_error_log(request: Request):
    if request.query_params.get("previous"):
        return _serve_log(request, ERROR_LOG_OLD, "(no previous generation)")
    return _serve_log(request, ERROR_LOG_FILE, "(no error log)")

@server.route("/health_log")
def route_health_log(request: Request):
    return _serve_log(request, HEALTH_LOG_FILE, "(no health log)")

@server.route("/clear_error_log", methods=["POST"])
def route_clear_error_log(request: Request):
    for name in (ERROR_LOG_FILE, ERROR_LOG_OLD):
        try: os.remove(f"{SD_PATH}/{name}")
        except OSError: pass
    return _json(request, {"ok": True})

@server.route("/clear_health_log", methods=["POST"])
def route_clear_health_log(request: Request):
    try: os.remove(f"{SD_PATH}/{HEALTH_LOG_FILE}")
    except OSError: pass
    return _json(request, {"ok": True})

@server.route("/remount_sd", methods=["POST"])
def route_remount_sd(request: Request):
    ok = mount_sd()
    return _json(request, {"ok": ok, "sd_status": intermediate.sd_status})

@server.route("/display_test", methods=["POST"])
def route_display_test(request: Request):
    intermediate.display_test_until = time.monotonic() + 8
    return _json(request, {"ok": bool(_lines), "display": display_info["type"]})

@server.route("/reset_crashes", methods=["POST"])
def route_reset_crashes(request: Request):
    try:
        microcontroller.nvm[NVM_IDX_CRASHES] = 0
    except Exception:
        pass
    return _json(request, {"ok": True})

async def task_server():
    i = intermediate
    last = time.monotonic()
    while True:
        try:
            server.poll()
        except ServerStoppedError:
            start_server()
        except MemoryError as e:
            # No cleanup helps reliably — save the trace, restart.
            log_error(f"MEMORYERROR in server: {e}  free={gc.mem_free()}  -> reset")
            microcontroller.reset()
        except Exception as e:
            # Counted instead of swallowed: an error in the TLS handshake
            # would otherwise look like nothing. Keep the text once per window.
            i.srv_errors += 1
            if i.srv_errors == 1:
                i.srv_error_txt = str(e)
        try:
            microcontroller.watchdog.feed()
        except Exception:
            pass

        # How long was the loop blocked? The health log reports above 6 s.
        now = time.monotonic()
        dt = now - last
        last = now
        i.loop_dt = i.loop_dt * 0.98 + dt * 0.02
        if dt > i.loop_dt_max:
            i.loop_dt_max = dt
            i.blocked_at = timestamp()
        await asyncio.sleep(0.05)

# ================= DISPLAY & SWITCH =================
# OLED text is user interface, so it stays German.
_SHELLY_TEXT = {"starting": "Start...", "searching": "suche Shelly",
                "ok": "Shelly OK", "offline": "Shelly offline"}

async def task_display():
    i = intermediate
    show_line(0, "Energy-Logger")
    show_line(1, f"v{EL_VERSION} Build {EL_BUILD}")
    await asyncio.sleep(3)
    while True:
        if time.monotonic() < i.display_test_until:
            # Test pattern: every line filled, type and address of the display
            d = display_info
            show_line(0, "#" * 21)
            show_line(1, "DISPLAY-TEST")
            show_line(2, d["type"].upper())
            show_line(3, f"Adresse {d['address'] and hex(d['address'])}")
            show_line(4, f"Erkennung: {d['how']}")
            show_line(5, "#" * 21)
            await asyncio.sleep(0.5)
            continue
        i.ap_ip = ap_address()
        show_line(0, f"P: {i.power:.1f} W")
        show_line(1, f"E: {i.energy:.1f} Wh")
        show_line(2, _SHELLY_TEXT.get(i.shelly_state, i.shelly_state) +
                  (" EIN" if i.output and i.shelly_ok else ""))
        show_line(3, f"SD: {i.sd_status}" + ("" if i.logging_enabled else " (Log aus)"))
        show_line(4, f"AP: {i.ap_ip or '-'}")
        if i.rtc_synced:
            t = rtc.RTC().datetime
            show_line(5, f"{t.tm_mday:02d}.{t.tm_mon:02d}. {t.tm_hour:02d}:{t.tm_min:02d}")
        else:
            show_line(5, "Uhr nicht gestellt")
        await asyncio.sleep(0.5)

# ================= MAIN =================
async def main():
    set_led(COLOR_OFF)
    mount_sd()
    _log_boot()
    if not HTTPS:
        log_error("NO CERTIFICATE  server.crt/server.key missing -> HTTP on port 80, "
                  "the PWA cannot be installed on iOS this way")

    try:
        wifi.radio.stop_ap()
    except Exception:
        pass
    try:
        wifi.radio.start_ap(ssid=AP_SSID, password=AP_PASSWORD)
    except Exception as e:
        log_error(f"AP START failed ({e}) — ap_password in secrets.py needs 8 to 63 characters")
        raise
    # The AP address appears a moment after start_ap(); only for the log.
    for _ in range(30):
        intermediate.ap_ip = ap_address()
        if intermediate.ap_ip:
            break
        await asyncio.sleep(0.1)
    print("[AP]", AP_SSID, intermediate.ap_ip)
    start_server()

    # From here on the server loop must run at least once a minute,
    # otherwise the watchdog resets the device.
    try:
        from watchdog import WatchDogMode
        microcontroller.watchdog.timeout = 60
        microcontroller.watchdog.mode = WatchDogMode.RESET
    except Exception as e:
        print("[WATCHDOG] not available:", e)

    await asyncio.gather(
        task_shelly(),
        task_sd_writer(),
        task_server(),
        task_display(),
        task_health(),
        task_healthy(),
    )

# An exception in any task tears down the whole program through gather().
# Without this block the reason would only appear on the serial console.
try:
    asyncio.run(main())
except Exception as _abort:
    try:
        import traceback
        _trace = "".join(traceback.format_exception(_abort))
    except Exception:
        _trace = repr(_abort)
    log_error("MAIN LOOP ABORTED\n" + _trace)
    raise          # the watchdog resets the device
