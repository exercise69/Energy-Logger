# Energy Logger Project

An Energy Logger based on **Shelly Plus Plug S Gen 2** and **QT-Py ESP32-S3** with CircuitPython Rev. 10.  
It captures energy consumption data, stores it on an SD card, and visualizes it via a local PWA/web interface.

---

## Project Overview

- Measures **energy consumption** of a device via Shelly Plus Plug S.
- **QT-Py ESP32-S3** collects the data and stores it on an SD card (`/sd`).
- Local display shows current measurement values.
- Serves a **PWA / Website** (`index.html`, `app.js`, `manifest.json`, `service-worker.js`, `style.css`) via its own Access Point network (`QT-LOGGER`).
- SD card is mounted under `/sd`, web files are located under `/html`.

---

## Hardware

- **Shelly Plus Plug S Generation 2** – measures energy consumption.
- **QT-Py ESP32-S3 (Adafruit)** – central control unit.
- **SD Card Module** – for local storage.
- **I²C Display** – display for energy consumption and status.
- **Optional:** Neopixel LED for status indications.

**Network:**

- Shelly provides an Access Point (AP).
- QT-Py connects to the Shelly in STA mode and simultaneously sets up its own AP (`QT-LOGGER`).
- **iOS WLAN Button:** Opens a shortcut that directly calls up the WLAN settings (`prefs:root=WIFI`). Only works on iPhone/iPad.
- PWA files (`index.html`, `app.js`, `style.css`, `manifest.json`, `service-worker.js`) are served via this AP.

---

## Software

- **CircuitPython rev. 10**
- Libraries: `adafruit_requests`, `adafruit_ntp`, `adafruit_minimqtt`, `adafruit_sdcard`, `displayio`, etc.
- **PWA:** Local operation and visualization.
- **Logging:** CSV and JSON files on SD card.
- **MQTT (optional):** Publishing data to an MQTT broker.

**Functions:**

- **Shelly Toggle:** Switch the Shelly relay on/off.
- **Logging Toggle:** Activate/deactivate the SD logging function.
- **Real-time Measurement:** Power (W), Energy (Wh), IPs, RTC status, SD card status.
- **Polling:** Continuous update of values on the PWA.
- **RTC Sync:** Time synchronization via NTP or Shelly.

---

## Installation / Deployment

1. Flash QT-Py with CircuitPython Rev. 10.
2. Copy libraries into the `lib/` folder.
3. Insert the SD card.
4. Connect the hardware (Display, Neopixel, SD card).
5. Copy the `/html` folder files to the QT-Py.
6. Create `secrets_shelly.py` with WLAN, Shelly, and optional MQTT credentials.
7. Connect the power supply.
8. Access the PWA via the `QT-LOGGER` Access Point.

---

## Operation

- QT-Py connects automatically to the Shelly.
- Local AP `QT-LOGGER` enables access to the PWA.
- Logging can be toggled via the PWA.
- Energy and status data are regularly updated and optionally logged to the SD card.
- The iOS Shortcut opens WLAN settings directly to simplify switching networks.

---

## Icons / Graphics

- The project icons (`icon-521.png`, `icon-192.png`, etc.) were created by the project author using AI assistance (ChatGPT) and specific design instructions.
- No third-party rights are violated. The icons may be used, published, and distributed within the scope of this project.
- License: **MIT / Public Domain** for the icons, provided no third-party logos or trademark rights are affected.

---

## Deployment Checklist

- [ ] Code cleanliness checked
- [ ] Unnecessary logs removed
- [ ] Comments placed meaningfully
- [ ] Formatting consistent
- [ ] SD card prepared and mounted
- [ ] HTML/JS/CSS in the `/html` directory
- [ ] `secrets_shelly.py` correctly configured
- [ ] WLAN and Shelly connection tested
- [ ] PWA tested in browser
- [ ] Logging function verified
- [ ] Shelly Toggle tested
- [ ] iOS WLAN shortcut tested
- [ ] MQTT tested (if applicable)

---

## License & Legal Notices

1. **Hardware Licenses:**

   - Shelly: Property of Allterco Robotics (Shelly Group). Use according to their guidelines.
   - QT-Py: Adafruit Hardware. No license restrictions for personal projects.

2. **Software Licenses:**

   - CircuitPython and libraries: Subject to their respective licenses (usually MIT or BSD).
   - Custom Code: MIT License recommended.

3. **ChatGPT / AI Assistance:**

   - Parts of the documentation, icons, and code assistance were generated with ChatGPT.
   - Responsibility for integration, operation, and correctness lies solely with the user.

4. **Disclaimer:** **The creator of this project assumes no responsibility, liability, compensation, or other obligations** for damage to hardware, software, or any other losses.  
   **The use of this project is entirely at the user's own risk.** Any damages, failures, or legal consequences are the sole responsibility of the user.

---

## Information for Contributors

- Please submit contributions via Pull Requests.
- Ensure code is cleanly formatted and remove unnecessary debug logs.
- Add meaningful comments.
- Coordinate new features with the maintainer beforehand.
- Do not remove license notices or disclaimers.
- Test all changes regarding Shelly communication, logging, iOS shortcuts, PWA delivery, and icons.

---

## Credits

- **Adafruit:** QT-Py, libraries, Neopixel, displays
- **Allterco Robotics:** Shelly hardware
- **OpenAI ChatGPT:** Support with documentation, icons, and code
