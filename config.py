# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Uwe Piro
# https://github.com/exercise69/Energy-Logger

# config.py — device settings. No credentials: those live in secrets.py,
# which is not committed.

config = {
    # Shelly Plus Plug S (Gen 2) in its own AP mode
    "shelly_ip": "192.168.33.1",   # factory default of the Shelly AP
    # Shelly poll interval in seconds. Below 5 s the Shelly gets into
    # trouble, so code.py never polls faster than every 5 s.
    "poll_interval": 10,

    # SD card
    "sd_cs_pin": "A1",
    "logging_enabled": True,

    # OLED on STEMMA QT. "auto" detects SSD1306 128x64 or SSD1327 128x128
    # by the status byte; set "ssd1306", "ssd1327" or "none" to force it.
    "display": "auto",
    "display_address": "auto",     # or 0x3D / 0x3C

    # Health log: one line of operating state every n seconds
    "health_interval": 300,
}
