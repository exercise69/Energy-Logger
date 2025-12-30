# Energy Logger Project

Ein Energy Logger basierend auf **Shelly Plus Plug S Gen 2** und **QT-Py ESP32-S3** mit CircuitPython Rev. 10.  
Es erfasst Energieverbrauchsdaten, speichert sie auf einer SD-Karte und stellt sie über eine lokale PWA/Weboberfläche dar.

---

## Projektübersicht

- Misst **Energieverbrauch** eines Geräts über Shelly Plus Plug S.
- **QT-Py ESP32-S3** sammelt die Daten und speichert sie auf einer SD-Karte (`/sd`).
- Lokales Display zeigt aktuelle Messwerte.
- Liefert eine **PWA / Webseite** aus (`index.html`, `app.js`, `manifest.json`, `service-worker.js`, `style.css`) über ein eigenes Access Point Netzwerk (`QT-LOGGER`).
- SD-Karte wird unter `/sd` gemountet, Webdateien liegen unter `/html`.

---

## Hardware

- **Shelly Plus Plug S Generation 2** – misst Energieverbrauch.
- **QT-Py ESP32-S3 (Adafruit)** – zentrale Steuereinheit.
- **SD-Kartenmodul** – für lokale Speicherung.
- **I²C Display** – Anzeige von Energieverbrauch und Status.
- **Optional:** Neopixel-LED für Statusanzeigen.

**Netzwerk:**

- Shelly stellt einen Access Point (AP).
- QT-Py verbindet sich im STA-Modus zum Shelly und baut gleichzeitig einen eigenen AP (`QT-LOGGER`) auf.
- **iOS WLAN-Button:** Öffnet einen Shortcut, der direkt die WLAN-Einstellungen aufruft (`prefs:root=WIFI`). Funktioniert nur auf iPhone/iPad.
- PWA-Dateien (`index.html`, `app.js`, `style.css`, `manifest.json`, `service-worker.js`) werden über diesen AP ausgeliefert.

---

## Software

- **CircuitPython rev. 10**
- Bibliotheken: `adafruit_requests`, `adafruit_ntp`, `adafruit_minimqtt`, `adafruit_sdcard`, `displayio` usw.
- **PWA:** lokale Bedienung und Visualisierung.
- **Logging:** CSV- und JSON-Dateien auf SD-Karte.
- **MQTT (optional):** Veröffentlichung der Daten auf einem MQTT-Broker.

**Funktionen:**

- Shelly Toggle: Ein-/Ausschalten des Shelly Switch.
- Logging Toggle: Aktivieren/Deaktivieren der SD-Logging-Funktion.
- Echtzeitmessung: Power (W), Energy (Wh), IPs, RTC-Status, SD-Kartenstatus.
- Polling: kontinuierliches Update der Werte auf PWA.
- RTC-Synchronisation über NTP oder Shelly.

---

## Installation / Deployment

1. QT-Py mit CircuitPython Rev. 10 flashen.
2. Bibliotheken in `lib/` kopieren.
3. SD-Karte einsetzen.
4. Hardware verbinden (Display, Neopixel, SD-Karte).
5. Dateien `/html` auf QT-Py kopieren.
6. `secrets_shelly.py` mit WLAN-, Shelly- und optionalen MQTT-Daten erstellen.
7. Stromversorgung anschließen.
8. Zugriff auf die PWA über den AP `QT-LOGGER`.

---

## Betrieb

- QT-Py verbindet sich automatisch zum Shelly.
- Lokaler AP `QT-LOGGER` ermöglicht Zugriff auf die PWA.
- Logging kann über die PWA ein-/ausgeschaltet werden.
- Energie- und Statusdaten werden regelmäßig aktualisiert und optional auf SD-Karte protokolliert.
- iOS Shortcut öffnet WLAN-Einstellungen direkt, um Netzwerkwechsel zu vereinfachen.

---

## Icons / Grafiken

- Die Projekt-Icons (`icon-521.png`, `icon-192.png` usw.) wurden vom Projektautor erstellt unter Verwendung von KI-Hilfe (ChatGPT) und eigenen Designanweisungen.
- Keine Rechte Dritter werden verletzt. Die Icons dürfen im Rahmen des Projekts genutzt, veröffentlicht und verteilt werden.
- Lizenz: **MIT / Public Domain** für die Icons, sofern keine Drittlogos oder Markenrechte verletzt werden.

---

## Checkliste für Deployment

- [ ] Code-Sauberkeit geprüft
- [ ] Unnötige Logs entfernt
- [ ] Kommentare sinnvoll platziert
- [ ] Formatierung konsistent
- [ ] SD-Karte vorbereitet und gemountet
- [ ] HTML/JS/CSS im `/html`-Verzeichnis
- [ ] `secrets_shelly.py` korrekt konfiguriert
- [ ] WLAN- und Shelly-Verbindung getestet
- [ ] PWA im Browser getestet
- [ ] Logging-Funktion überprüft
- [ ] Shelly Toggle getestet
- [ ] iOS WLAN-Shortcut getestet
- [ ] MQTT optional getestet

---

## Lizenz & rechtliche Hinweise

1. **Hardware-Lizenzen:**

   - Shelly: Eigentum von Allterco Robotics. Nutzung gemäß deren Richtlinien.
   - QT-Py: Adafruit Hardware. Keine Lizenzbeschränkungen für eigene Projekte.

2. **Software-Lizenzen:**

   - CircuitPython und Bibliotheken: je nach Lizenz (meist MIT oder BSD).
   - Eigenentwickelter Code: MIT License empfohlen.

3. **ChatGPT / KI-Hilfe:**

   - Teile der Dokumentation, Icons und Codehilfen wurden mit ChatGPT erstellt.
   - Verantwortung für Integration, Betrieb und Korrektheit liegt beim Nutzer.

4. **Haftungsausschluss (Disclaimer):**  
   **Der Ersteller dieses Projekts übernimmt keinerlei Verantwortung, Haftung, Entschädigung oder sonstige Verpflichtungen** für Schäden an Hardware, Software oder sonstige Verluste.  
   **Die Nutzung dieses Projekts erfolgt vollständig auf eigenes Risiko der Nutzer.**  
   Jegliche Schäden, Ausfälle oder rechtliche Konsequenzen liegen ausschließlich in der Verantwortung der Anwender.

---

## Hinweise für Contributors

- Beiträge bitte über Pull Requests.
- Code sauber formatieren, unnötige Logs entfernen.
- Kommentare sinnvoll setzen.
- Neue Features vorher mit Maintainer absprechen.
- Lizenzhinweise und Disclaimer nicht entfernen.
- Teste alle Änderungen auf funktionierende Shelly-Kommunikation, Logging, iOS Shortcut, PWA-Auslieferung und Icons.

---

## Credits

- **Adafruit:** QT-Py, Bibliotheken, Neopixel, Displays
- **Allterco Robotics:** Shelly Hardware
- **OpenAI ChatGPT:** Unterstützung bei Dokumentation, Icons und Code
