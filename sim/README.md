# Energy-Logger — simulator

Runs the **real `code.py`** on the Mac. Hardware is replaced by stand-ins, the
Shelly by a model. `code.py`, `config.py` and `html/` are **not** changed — all
adaptations live in `sim/simlib/`. (Built after the SolarLoader simulator.)

## Start

```bash
python3 sim/run_sim.py
```

| | |
|---|---|
| **http://127.0.0.1:8080/** | the device's web UI — the real `html/` |
| **http://127.0.0.1:8081/** | control panel: Shelly offline, Wi-Fi gone, SD card pulled, … |

Options:

```bash
python3 sim/run_sim.py --reset-sd      # empty the stand-in SD card (sim/sd/)
python3 sim/run_sim.py --no-sd         # boot without an SD card
python3 sim/run_sim.py --shelly-time   # the Shelly already has a time
python3 sim/run_sim.py --load 2000     # load on the plug in W
python3 sim/run_sim.py --poll 10       # poll_interval
python3 sim/run_sim.py --display ssd1327   # ssd1306 | ssd1327 | none | unknown
```

Stop with Ctrl-C. Plain HTTP, no certificate — `code.py` then reports
"NO CERTIFICATE" in the error log, as it would on a device without one.

## What the stand-ins check

They are deliberately strict, so the simulator finds what the device would hit:

| Stand-in | Catches |
|---|---|
| pins can be claimed once only | "A1 in use" on a remount that does not release the pin |
| open HTTP responses are counted | socket leaks (`open_responses` in `/sim/state`) |
| every Shelly request is timed | violations of the 5 s rule (`min_gap_s`) |
| watchdog is watched | a loop that blocks for more than 60 s (`watchdog_trips`) |
| I2C bus with the display's status byte | display detection, bus left locked |
| AP address appears 1 s after start_ap() | server started on a not-yet-known address |
| RTC starts at 2000-01-01 | code that relies on a set clock |
| SD card only reachable while mounted | writes after the card is gone |
| "error after write" fault | duplicate lines (the SolarLoader's sdcardio fault) |

## Tests

```bash
python3 sim/tests/dst.py           # instant: CET/CEST rule
python3 sim/tests/routes.py        # ~30 s: all routes, clock, toggle, download
python3 sim/tests/shelly_link.py   # ~2 min: request spacing, failures, recovery
python3 sim/tests/sd_robust.py     # ~1.5 min: missing card, remount, duplicates, month rotation
python3 sim/tests/display.py       # ~1 min: display detection, all four cases
```

Each test starts and stops its own simulator (ports 8080 and 8081 must be free).

## Not simulated

TLS, real memory pressure (`gc.mem_free()` is fixed), timing of the ESP32 Wi-Fi
radio, the OLED pixels (the text lines are in `/sim/state`).
