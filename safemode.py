# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Uwe Piro
# https://github.com/exercise69/Energy-Logger

# safemode.py — runs when CircuitPython enters safe mode.
#
# In safe mode neither boot.py nor code.py runs: no measuring, no logging, no
# watchdog. Without this file the device sits there until somebody pulls the
# plug — and the reason is lost, because the next boot counts as POWER_ON.
#
# This file writes the reason to the SD card and resets. So that a permanent
# hardware fault does not cause a reset loop, NVM byte 2 counts consecutive
# self-heals. After MAX_SELF_HEAL the device deliberately stays in safe mode —
# then a human should look. code.py clears the counter once a boot has run
# for 60 s.
#
# (Taken from the SolarLoader, pins adapted to the QT Py ESP32-S3.)

import time

MAX_SELF_HEAL    = 3
NVM_IDX_SAFEMODE = 2       # 0 and 1 belong to code.py (boot flag, crash counter)
SD_PATH          = "/sd"
ERROR_LOG        = "/sd/error_log.txt"


def _reason():
    """Safe mode reason as text — and whether we may reset."""
    try:
        import supervisor
        reason = supervisor.runtime.safe_mode_reason
        text = str(reason)
        # Triggered by hand or on purpose by the program: do not interfere.
        for name in ("USER", "PROGRAMMATIC", "NONE"):
            member = getattr(supervisor.SafeModeReason, name, None)
            if member is not None and reason == member:
                return text, False
        return text, True
    except Exception as e:
        return f"unknown ({e})", True


def _read_counter():
    try:
        import microcontroller
        return microcontroller.nvm[NVM_IDX_SAFEMODE]
    except Exception:
        return 0


def _write_counter(value):
    try:
        import microcontroller
        microcontroller.nvm[NVM_IDX_SAFEMODE] = min(value, 255)
    except Exception:
        pass


def _log(line):
    """Write a line to the SD card. Fails silently if there is none."""
    cs = None
    try:
        import board, digitalio, storage, adafruit_sdcard
        try:
            from config import config
            cs_pin = config.get("sd_cs_pin", "A1")
        except Exception:
            cs_pin = "A1"
        cs = digitalio.DigitalInOut(getattr(board, cs_pin))
        sd = adafruit_sdcard.SDCard(board.SPI(), cs)
        storage.mount(storage.VfsFat(sd), SD_PATH)
        with open(ERROR_LOG, "a") as f:
            f.write(line)
        try:
            storage.umount(SD_PATH)
        except Exception:
            pass
        return True
    except Exception as e:
        print("[SAFE] SD not writable:", e)
        return False
    finally:
        if cs is not None:
            try:
                cs.deinit()
            except Exception:
                pass


def run():
    text, may_reset = _reason()
    count = _read_counter() + 1

    print(f"[SAFE] safe mode: {text}  (attempt {count})")

    # The RTC is not set after a crash — uptime is better than a made-up time.
    _log(f"T+{time.monotonic():.0f}s  SAFE MODE  reason={text}  "
         f"selfheal={count}/{MAX_SELF_HEAL}\n")

    if not may_reset:
        print("[SAFE] triggered by hand — no reset.")
        return

    if count > MAX_SELF_HEAL:
        print("[SAFE] too many self-heals — staying here, please check.")
        _log(f"T+{time.monotonic():.0f}s  SAFE MODE  "
             f"gave up after {MAX_SELF_HEAL} attempts\n")
        return

    _write_counter(count)
    print("[SAFE] reset in 3 s...")
    time.sleep(3)          # time for the SD card write
    import microcontroller
    microcontroller.reset()


run()
