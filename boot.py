# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Uwe Piro
# https://github.com/exercise69/Energy-Logger

# boot.py — write-protect jumper on A0
#
# A0 open (normal operation): CIRCUITPY is writable from the computer,
#                             code.py cannot write to the internal drive.
# A0 to GND:                  code.py may write to CIRCUITPY, the computer
#                             only reads.
#
# All logs live on the SD card, not on CIRCUITPY — so A0 stays open in normal
# operation. code.py resets when the jumper is removed.

import board
import digitalio
import storage

switch = digitalio.DigitalInOut(board.A0)
switch.direction = digitalio.Direction.INPUT
switch.pull = digitalio.Pull.UP

storage.remount("/", readonly=switch.value)
switch.deinit()   # release A0, code.py reads the jumper itself
