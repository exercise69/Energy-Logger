# Energy-Logger

*Deutsche Fassung: [README-DE.md](README-DE.md)*

Energy logger built from a **Shelly Plus Plug S (Gen 2)** and an **Adafruit QT Py
ESP32-S3** running CircuitPython 10. It reads power and energy from the Shelly,
logs them to an SD card, shows them on a small OLED and serves an installable,
offline-capable web app (PWA) over **HTTPS** on its own Wi-Fi access point.

---

## How it works

```
 Phone ──Wi-Fi──▶ Energy-Logger AP (192.168.4.1, HTTPS)
                        │
                 QT Py ESP32-S3 ──Wi-Fi (station)──▶ Shelly AP (192.168.33.1)
                        │
                  SD card · OLED · NeoPixel
```

- The QT Py joins the Shelly's own access point and polls
  `Shelly.GetStatus` every `poll_interval` seconds (**never faster than 5 s**,
  the Shelly gets into trouble otherwise).
- At the same time it runs its own access point. The phone connects to it and
  opens `https://192.168.4.1`.
- Every reading is appended to `energy_log.csv` on the SD card. On a month change
  the file is renamed to `energy_log_YYYY-MM.csv` and a new one is started.

## Hardware

| Part | Connection |
|---|---|
| Adafruit QT Py ESP32-S3 (4 MB flash, 2 MB PSRAM) | — |
| SD card: Adafruit Micro SD Card BFF (5683) or other 3.3 V breakout | SPI (SCK/MOSI/MISO), CS on **A1** (BFF: solder jumper A1, default is TX) |
| OLED SSD1306 128×64 **or** SSD1327 128×128 | STEMMA QT / I²C, 0x3D or 0x3C — detected automatically |
| White LED (optional) | **A0** via resistor to GND — reserved, no function yet |
| Shelly Plus Plug S Gen 2 | in AP mode, factory IP 192.168.33.1 |

## Files on the device (CIRCUITPY)

```
CIRCUITPY/
├─ code.py            main program
├─ safemode.py        logs the reason of a safe-mode crash and resets
├─ config.py          device settings (no credentials)
├─ secrets.py         Wi-Fi credentials — copy from secrets_example.py
├─ server.crt         TLS certificate for 192.168.4.1
├─ server.key         TLS key
├─ sd/                empty folder — mount point of the SD card (required!)
├─ html/              the web app (index.html, app.js, style.css, …)
└─ lib/               libraries from the Adafruit bundle
```

`secrets.py`, `server.crt`, `server.key` and `lib/` are **not** in the repository.

### Libraries

From the CircuitPython 10.x bundle: `adafruit_httpserver`, `adafruit_requests`,
`adafruit_connection_manager`, `adafruit_sdcard`, `adafruit_bus_device`,
`adafruit_displayio_ssd1306`, `adafruit_display_text`, `asyncio`, `adafruit_ticks`,
`neopixel`, `adafruit_pixelbuf`, `adafruit_ssd1327`.

Use **`adafruit_sdcard`**, not `sdcardio` — on the sister project SolarLoader
`sdcardio` caused write errors and duplicate lines in the field.

## Setup

1. Flash CircuitPython 10.x for the QT Py ESP32-S3.
2. Copy `lib/`, `html/`, `code.py`, `safemode.py`, `config.py` to CIRCUITPY
   and create an empty folder `sd` there (CircuitPython 10 needs the mount point).
3. Copy `secrets_example.py` to `secrets.py` and fill in your values.
   `ap_password` needs 8 to 63 characters.
4. Put `server.crt` and `server.key` for `192.168.4.1` on the device. Without them
   the logger falls back to plain HTTP on port 80 — that works in a browser, but
   the PWA cannot be installed on iOS.
5. Insert the SD card, connect the Shelly, power up.
6. Join the Wi-Fi `Energy-Logger` on your phone and open `https://192.168.4.1`.

The clock has no battery and no internet. The app sends the phone's time
automatically when it opens and the logger reports an unset clock. If the Shelly
has a time itself, it is used as well.

## Display detection

At boot the logger scans the I²C bus (0x3D, 0x3C) and reads one status byte from
the display. The SSD1327 answers `0x02` (measured), the SSD1306 `0x03`/`0x43`
(datasheet). Unknown bytes fall back to SSD1306. The result is in the BOOT line
of the error log and under *Diagnose* in the app, where *Display testen* shows a
test pattern. If the detection is ever wrong, force the type in `config.py`
(`"display": "ssd1306"`, `"ssd1327"` or `"none"`).

## Web app

- Live power, energy, voltage/current, switch the plug on and off
- SD card, logging and clock status; pause/resume logging; set the clock by hand
- Download of the data log per month (in pieces, can be aborted)
- **Diagnose**: software version of device and UI, uptime, crashes, memory,
  loop time, server errors, error log, health log, connection log of the phone

The app polls the logger every 5 s while you look at it, every 30 s after
3 minutes without touching it, and not at all in the background.

## Robustness

Taken over from the SolarLoader:

- **Watchdog** (60 s) — a hung program resets itself
- **Crash detection** in NVM, every boot is written to `error_log.txt`
- **`safemode.py`** writes the safe-mode reason to the SD card and resets
  (at most 3 times in a row)
- **Health log** `health_log.csv`: memory, largest block, CPU temperature, loop
  time, slowest Shelly request and SD write — every 5 minutes
- SD card is **remounted automatically**, a write reported as failed is never
  written twice, logs are rotated instead of deleted

## Development

```bash
python3 sim/run_sim.py          # runs the real code.py on the Mac, see sim/README.md
python3 sim/tests/dst.py        # quick unit test
# on the device: copy tools/sd_debug.py to CIRCUITPY, Ctrl-C, then `import sd_debug`
python3 tools/stamp.py --check  # version in code.py, app.js and service worker agree
python3 tools/stamp.py 2.1 "short description"   # before a release, then commit
```

Code, identifiers and comments are in English; the user interface is German.

## iOS shortcut

The "WLAN wechseln" button opens an iOS shortcut named `ChangeWIFI`, see
[ChangeWIFI.md](ChangeWIFI.md).

## License

MIT, see [LICENSE.txt](LICENSE.txt). Shelly is a product of Shelly Group
(formerly Allterco Robotics); this project is not affiliated with it.

**Disclaimer:** use at your own risk. The author accepts no liability for damage
to hardware, software or anything else.
