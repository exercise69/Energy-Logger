# Energy Logger Project

An energy logger based on **Shelly Plus Plug S Gen 2** and **QT-Py ESP32-S3** running CircuitPython Rev. 10.  
It records energy consumption data, stores it on an SD card, and serves it via a local **PWA/web interface with HTTPS**.  
The application is **offline-capable** and can be installed as an app.

---

## Project Overview

- Measures **energy consumption** of a device via Shelly Plus Plug S.
- **QT-Py ESP32-S3** collects the data and stores it on an SD card (`/sd`).
- Local display shows real-time measurements.
- Serves a **PWA / website** (`index.html`, `app.js`, `manifest.json`, `service-worker.js`, `style.css`) via its own access point (`QT-LOGGER`).
- **New: HTTPS support with self-signed certificate**  
  → required for **PWA & Service Worker on iOS**.
- SD card mounted at `/sd`, web files under `/html`.

---

## Hardware

- **Shelly Plus Plug S Generation 2** – measures energy consumption.
- **QT-Py ESP32-S3 (Adafruit)** – main controller.
- **SD card module** – for local storage.
- **I²C display** – shows energy and system status.
- **Optional:** Neopixel LED for status indication.

**Network:**

- Shelly provides an access point (AP).
- QT-Py connects to Shelly in STA mode while also running its own AP (`QT-LOGGER`).
- **iOS Wi-Fi Shortcut:** Opens Wi-Fi settings directly (`prefs:root=WIFI`). Only works on iPhone/iPad.
- PWA files (`index.html`, `app.js`, `style.css`, `manifest.json`, `service-worker.js`) are served via this AP.
- **HTTPS runs on port 443** with certificate (`server.crt`) and key (`server.key`).

---

## Software

- **CircuitPython Rev. 10**
- Libraries: `adafruit_requests`, `adafruit_ntp`, `adafruit_minimqtt`, `adafruit_sdcard`, `displayio`, etc.
- **PWA:** local control and visualization.
- **Service Worker:** offline cache, app-installable.
- **Logging:** CSV and JSON files on SD card.
- **MQTT (optional):** publish data to an MQTT broker.

**Features:**

- Shelly Toggle: switch Shelly on/off.
- Logging Toggle: enable/disable SD logging.
- Real-time measurements: Power (W), Energy (Wh), IPs, RTC status, SD card status.
- Polling: continuous update of values on PWA.
- RTC synchronization via NTP or Shelly.
- **Fallback time when no real-time clock is available** → default: `2026-01-01`.

---

## SD Logging (Updated)

The SD logging logic now uses a **queue** to prevent data loss:

- Buffer up to 100 entries
- Automatic retry on SD errors
- Remount SD card on failures
- Drop counter on queue overflow
- LED feedback for status

### Logging Status Values:

| Value     | Meaning                   |
| --------- | ------------------------- |
| `off`     | Logging disabled          |
| `idle`    | Queue empty               |
| `writing` | Current write in progress |
| `ok`      | Last write successful     |
| `error`   | SD problem                |

These status values are also shown on the display and in the web interface.

---

## Service Worker & HTTPS

To make the PWA work on iOS:

- Service Worker is served at `/service-worker.js`
- Correct MIME type: `application/javascript`
- **HTTPS mandatory**, running on port 443
- Offline-capable
- App-installable

**Note:** Browser warnings due to self-signed certificate are normal.

---

## Installation / Deployment

1. Flash QT-Py with CircuitPython Rev. 10.
2. Copy libraries to `lib/`.
3. Insert SD card.
4. Connect hardware (display, Neopixel, SD card).
5. Copy web files to `/html`.
6. Create `secrets_shelly.py` with Wi-Fi, Shelly, and optional MQTT credentials.
7. **Save HTTPS certificate & key (`server.crt`, `server.key`)**
8. Connect power.
9. Access the PWA via AP `QT-LOGGER`: https://192.168.4.1

---

## Operation

- QT-Py automatically connects to the Shelly.
- Local AP `QT-LOGGER` provides access to the PWA.
- Logging can be toggled via the PWA.
- Energy and status data are updated regularly and optionally logged to the SD card.
- iOS shortcut opens Wi-Fi settings directly for easier network switching.
- Service Worker enables **offline usage**.

---

## Icons / Graphics

- Project icons (`icon-521.png`, `icon-192.png`, etc.) were created by the project author using AI assistance (ChatGPT) and custom design instructions.
- No third-party rights are infringed. Icons may be used, published, and distributed within the project.
- License: **MIT / Public Domain** for icons, provided no third-party logos or trademarks are violated.

---

## Deployment Checklist

- [ ] Code reviewed for cleanliness
- [ ] Unnecessary logs removed
- [ ] Comments placed meaningfully
- [ ] Formatting consistent
- [ ] SD card prepared and mounted
- [ ] HTML/JS/CSS in `/html` folder
- [ ] `secrets_shelly.py` correctly configured
- [ ] Wi-Fi and Shelly connection tested
- [ ] **HTTPS working**
- [ ] **Service Worker active**
- [ ] PWA tested in browser
- [ ] Logging functionality verified
- [ ] Shelly Toggle tested
- [ ] iOS Wi-Fi shortcut tested
- [ ] MQTT optionally tested

---

## License & Legal Notes

1. **Hardware Licenses:**

   - Shelly: property of Allterco Robotics. Usage according to their policies.
   - QT-Py: Adafruit hardware. No license restrictions for personal projects.

2. **Software Licenses:**

   - CircuitPython and libraries: according to license (mostly MIT or BSD).
   - Own code: MIT License recommended.

3. **ChatGPT / AI Assistance:**

   - Parts of the documentation, icons, and code helpers were created with ChatGPT.
   - Responsibility for integration, operation, and correctness lies with the user.

4. **Disclaimer:**  
   **The creator of this project assumes no responsibility, liability, compensation, or any obligations** for damages to hardware, software, or other losses.  
   **Use of this project is entirely at the user's own risk.**

---

## Notes for Contributors

- Submit contributions via Pull Requests.
- Format code cleanly, remove unnecessary logs.
- Place comments meaningfully.
- Discuss new features with the maintainer beforehand.
- Do not remove license notices or disclaimers.
- Test all changes for working Shelly communication, logging, iOS shortcut, PWA delivery, and icons.
- **When editing the Service Worker:** users may need to reinstall the PWA.
- **HTTPS is required for PWA on iOS.**

---

## Credits

- **Adafruit:** QT-Py, libraries, Neopixels, displays
- **Allterco Robotics:** Shelly hardware
- **OpenAI ChatGPT:** support for documentation, icons, and code
