# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Uwe Piro
# https://github.com/exercise69/Energy-Logger

# sd_debug.py — step-by-step SD card diagnosis on the device itself.
#
# Copy to CIRCUITPY, stop code.py (Ctrl-C in the serial console), then:
#
#     import sd_debug          # full diagnosis, steps 1-4
#     sd_debug.wiggle()        # live monitor: wiggle one wire after another
#
# The steps go from the bottom up, so the first failing step points at the
# cause:
#   1. pins    each line on its own: stuck to GND or 3.3 V?
#   2. CMD0    raw SPI, no library: does the card answer at all?
#   3. CMD8    is a data pattern echoed correctly (MOSI and MISO both fine)?
#   4. repeat  50 times at three clock speeds: stable or flaky?
#   4b. init   ACMD41 until ready — the card's peak current, tests the supply
#   5. mount   adafruit_sdcard + file write/read-back
# User-facing output is German, like the rest of the UI.

import time
import board
import busio
import digitalio

try:
    from config import config
    CS_PIN = config.get("sd_cs_pin", "A1")
except Exception:
    CS_PIN = "A1"

PINS = (("SCK", "SCK"), ("MOSI", "MOSI"), ("MISO", "MISO"), ("CS", CS_PIN))

try:
    import neopixel
    _pixel = neopixel.NeoPixel(board.NEOPIXEL, 1, brightness=0.15)
except Exception:
    _pixel = None


def _led(color):
    if _pixel is not None:
        _pixel[0] = color


# ── Step 1: pin levels ──────────────────────────────────────────
def check_pins():
    """Read every line once with pull-up and once with pull-down.

    A free or correctly wired line follows the pull. A line that reads the same
    with both pulls is driven hard: shorted to GND/3.3 V, or actively driven by
    the card (MISO may do that). This finds shorts, not open wires.
    """
    print("\n== 1. Leitungen einzeln (Pull-up / Pull-down)")
    ok = True
    for name, pin_name in PINS:
        pin = digitalio.DigitalInOut(getattr(board, pin_name))
        pin.direction = digitalio.Direction.INPUT
        pin.pull = digitalio.Pull.UP
        time.sleep(0.01)
        up = pin.value
        pin.pull = digitalio.Pull.DOWN
        time.sleep(0.01)
        down = pin.value
        pin.deinit()
        if up and not down:
            verdict = "ok (folgt dem Pull)"
        elif not up and not down:
            verdict = "liegt fest auf GND — Kurzschluss nach Masse?"
            ok = ok and name == "MISO"
        elif name == "CS":
            # Most SD breakouts pull CS up with 10 kOhm — stronger than the
            # internal pull-down, so this is normal
            verdict = "liegt auf 3,3 V — normal bei Pull-up-Widerstand auf dem Modul"
        else:
            verdict = "liegt fest auf 3,3 V — Kurzschluss nach VCC?"
            ok = ok and name == "MISO"
        print(f"   {name:5} ({pin_name:4})  up={int(up)} down={int(down)}  {verdict}")
    print("   Hinweis: MISO darf fest liegen, wenn die Karte die Leitung treibt.")
    return ok


# ── Raw SPI ─────────────────────────────────────────────────────
class RawCard:
    """Minimal SD SPI protocol — just enough to see what comes back."""

    def __init__(self, baudrate):
        self.spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)
        self.cs = digitalio.DigitalInOut(getattr(board, CS_PIN))
        self.cs.direction = digitalio.Direction.OUTPUT
        self.cs.value = True
        while not self.spi.try_lock():
            pass
        self.spi.configure(baudrate=baudrate, phase=0, polarity=0)

    def close(self):
        try:
            self.spi.unlock()
        except Exception:
            pass
        self.spi.deinit()
        self.cs.deinit()

    def wake(self):
        # At least 74 clocks with CS high put the card into native mode
        self.cs.value = True
        self.spi.write(b"\xff" * 10)

    def command(self, cmd, arg, crc, extra=0):
        """Send a command, return (R1, extra response bytes, all bytes seen)."""
        frame = bytes([0x40 | cmd, (arg >> 24) & 0xFF, (arg >> 16) & 0xFF,
                       (arg >> 8) & 0xFF, arg & 0xFF, crc])
        self.cs.value = False
        self.spi.write(b"\xff")
        self.spi.write(frame)
        seen = bytearray()
        r1 = 0xFF
        buf = bytearray(1)
        for _ in range(10):                 # the answer comes within 8 bytes
            self.spi.readinto(buf, write_value=0xFF)
            seen.append(buf[0])
            if not buf[0] & 0x80:
                r1 = buf[0]
                break
        rest = bytearray(extra)
        if extra and r1 != 0xFF:
            self.spi.readinto(rest, write_value=0xFF)
        self.cs.value = True
        self.spi.write(b"\xff")
        return r1, bytes(rest), bytes(seen)


def _explain_r1(r1, seen):
    if r1 == 0x01:
        return "ok — Karte antwortet (Idle)"
    if r1 == 0x00:
        return "Karte antwortet (bereit)"
    if all(b == 0xFF for b in seen):
        return ("nur 0xFF: keine Antwort. MISO offen, CS kommt nicht an, "
                "Karte ohne Strom oder nicht gesteckt")
    if all(b == 0x00 for b in seen):
        return "nur 0x00: MISO liegt auf GND (Kurzschluss) oder Karte ohne Strom"
    return "unerwartete Bytes: gestörte Leitung (SCK/MOSI) oder Takt zu hoch"


def handshake(card):
    """CMD0 + CMD8. Returns (ok, text)."""
    card.wake()
    r1, _, seen = card.command(0, 0, 0x95)
    if r1 != 0x01:
        return False, f"CMD0 → {seen.hex()}: {_explain_r1(r1, seen)}"
    r1, r7, seen = card.command(8, 0x1AA, 0x87, extra=4)
    if r1 & 0x04:
        return True, "CMD0 ok, CMD8 unbekannt → alte Karte (SD v1), Echo-Test nicht möglich"
    if r1 != 0x01:
        return False, f"CMD8 → {seen.hex()}: {_explain_r1(r1, seen)}"
    if r7[2] & 0x0F != 0x01 or r7[3] != 0xAA:
        return False, (f"CMD8 Echo falsch ({r7.hex()}, erwartet ...01aa): "
                       "einzelne Bits kippen — MOSI/MISO/SCK wackelt")
    return True, f"CMD0 ok, CMD8 Echo {r7.hex()} ok"


# ── Steps 2-4 ───────────────────────────────────────────────────
def check_raw():
    print("\n== 2./3. Rohe SPI-Antwort (250 kHz, ohne Bibliothek)")
    card = RawCard(250000)
    try:
        ok, text = handshake(card)
    finally:
        card.close()
    print("   " + ("OK   " if ok else "FEHL ") + text)
    return ok


def check_repeat(n=50):
    print(f"\n== 4. {n} Durchläufe je Takt — stabil oder wackelig?")
    results = {}
    for baud in (250000, 1320000, 4000000):
        card = RawCard(baud)
        good, first_err = 0, ""
        try:
            for _ in range(n):
                ok, text = handshake(card)
                if ok:
                    good += 1
                elif not first_err:
                    first_err = text
        finally:
            card.close()
        results[baud] = good
        note = "" if good == n else f"   erster Fehler: {first_err}"
        print(f"   {baud / 1e6:4.2f} MHz: {good:2}/{n} ok{note}")
    print("   (adafruit_sdcard arbeitet mit 1,32 MHz)")
    if results[250000] == n and results[1320000] < n:
        print("   → Langsam stabil, schneller nicht: lange/lose Kabel, Takt-Leitung "
              "(SCK) zuerst prüfen.")
    elif 0 < results[250000] < n:
        print("   → Schon langsam wackelig: echter Wackelkontakt. Weiter mit "
              "sd_debug.wiggle().")
    return all(v == n for v in results.values())


def check_init(seconds=3.0):
    """CMD55+ACMD41 until the card reports ready — the step where its
    controller starts up and draws the most current. Signals fine but stuck
    here points at the power supply (3V/GND contact, breadboard rails)."""
    print("\n== 4b. Karte hochfahren (ACMD41) — hier zieht sie den meisten Strom")
    card = RawCard(250000)
    try:
        ok, text = handshake(card)
        if not ok:
            print("   FEHL " + text)
            return False
        t0 = time.monotonic()
        tries = 0
        answers = {}
        while time.monotonic() - t0 < seconds:
            card.command(55, 0, 0x65)
            r1, _, _ = card.command(41, 0x40000000, 0x77)
            tries += 1
            answers[r1] = answers.get(r1, 0) + 1
            if r1 == 0x00:
                dt = time.monotonic() - t0
                r1, ocr, _ = card.command(58, 0, 0xFD, extra=4)
                kind = "SDHC/SDXC" if ocr[0] & 0x40 else "SDSC"
                print(f"   OK   bereit nach {dt * 1000:.0f} ms ({tries} Versuche), "
                      f"OCR {ocr.hex()} → {kind}")
                return True
            time.sleep(0.01)
        summary = ", ".join(f"0x{k:02x}×{v}" for k, v in answers.items())
        print(f"   FEHL nach {seconds:.0f} s nicht bereit ({tries} Versuche, Antworten {summary})")
        if 0x01 in answers and len(answers) == 1:
            print("   → Karte antwortet, wird aber nie fertig. Typisch für zu wenig Strom: "
                  "3V- und GND-Leitung zum Modul prüfen (Breadboard-Schiene!), "
                  "eine andere Karte probieren.")
        else:
            print("   → Antworten wechseln: Kontakt geht während des Hochfahrens verloren "
                  "— Versorgung oder Kartensitz.")
        return False
    finally:
        card.close()


def check_mount():
    print("\n== 5. Einbinden mit adafruit_sdcard, Datei schreiben und zurücklesen")
    import adafruit_sdcard
    import storage
    import os
    spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)
    cs = digitalio.DigitalInOut(getattr(board, CS_PIN))
    try:
        sd = adafruit_sdcard.SDCard(spi, cs)
        print(f"   Karte erkannt, {sd.count() * 512 / 1e9:.1f} GB")
        storage.mount(storage.VfsFat(sd), "/sd")
        data = "".join(f"Zeile {i:04d} Energy-Logger SD-Test\n" for i in range(200))
        t0 = time.monotonic()
        with open("/sd/_sd_debug.txt", "w") as f:
            f.write(data)
        t1 = time.monotonic()
        with open("/sd/_sd_debug.txt", "r") as f:
            back = f.read()
        t2 = time.monotonic()
        os.remove("/sd/_sd_debug.txt")
        same = back == data
        print(f"   {len(data)} Bytes geschrieben in {t1 - t0:.2f} s, gelesen in "
              f"{t2 - t1:.2f} s, Vergleich {'ok' if same else 'FALSCH'}")
        print(f"   Dateien auf der Karte: {os.listdir('/sd')[:8]}")
        storage.umount("/sd")
        return same
    except Exception as e:
        print(f"   FEHL {type(e).__name__}: {e}")
        return False
    finally:
        spi.deinit()
        cs.deinit()


def run():
    print("SD-Diagnose — CS an", CS_PIN)
    results = [("Leitungen", check_pins()), ("Antwort", check_raw())]
    if results[-1][1]:
        results.append(("Wiederholung", check_repeat()))
        results.append(("Hochfahren", check_init()))
        results.append(("Einbinden/Datei", check_mount()))
    print("\n== Ergebnis")
    for name, ok in results:
        print(f"   {'OK  ' if ok else 'FEHL'} {name}")
    if not results[1][1]:
        print("   → Die Karte antwortet nicht. Reihenfolge zum Prüfen: Stromversorgung "
              "(3V/GND), CS, MISO, SCK, MOSI. Danach sd_debug.wiggle().")
    print("\nWackel-Test starten:  sd_debug.wiggle()   (Ende mit Ctrl-C)")


def wiggle(baud=1320000, interval=0.3):
    """Live monitor. Wiggle one wire after another; LED red = contact lost."""
    print(f"Wackel-Test bei {baud / 1e6:.2f} MHz — Kabel einzeln bewegen. Ctrl-C beendet.")
    print("LED grün = Karte antwortet, rot = Fehler.\n")
    card = RawCard(baud)
    good = bad = streak = 0
    last_ok = None
    try:
        while True:
            ok, text = handshake(card)
            if ok:
                good += 1
                _led((0, 60, 0))
            else:
                bad += 1
                _led((80, 0, 0))
            if ok != last_ok:              # print only changes, plus a heartbeat
                stamp = f"{time.monotonic():8.1f}s"
                print(f"{stamp}  {'OK  ' if ok else 'FEHL'}  ok={good} fehl={bad}  "
                      f"{'' if ok else text}")
                last_ok = ok
                streak = 0
            else:
                streak += 1
                if streak % 20 == 0:
                    print(f"{time.monotonic():8.1f}s  ... ok={good} fehl={bad}")
            time.sleep(interval)
    except KeyboardInterrupt:
        print(f"\nEnde: ok={good} fehl={bad}")
    finally:
        card.close()
        _led((0, 0, 0))


run()
