# Energy Logger Project

Ein Energy Logger basierend auf **Shelly Plus Plug S Gen 2** und **QT-Py ESP32-S3** mit CircuitPython Rev. 10.  
Es erfasst Energieverbrauchsdaten, speichert sie auf einer SD-Karte und stellt sie über eine lokale **PWA/Weboberfläche mit HTTPS** dar.  
Die Anwendung ist **offline-fähig** und kann als App installiert werden.

---

## Projektübersicht

- Misst **Energieverbrauch** eines Geräts über Shelly Plus Plug S.
- **QT-Py ESP32-S3** sammelt die Daten und speichert sie auf einer SD-Karte (`/sd`).
- Lokales Display zeigt aktuelle Messwerte.
- Liefert eine **PWA / Webseite** aus (`index.html`, `app.js`, `manifest.json`, `service-worker.js`, `style.css`) über ein eigenes Access Point Netzwerk (`QT-LOGGER`).
- **Neu: HTTPS-Betrieb mit selbstsigniertem Zertifikat**  
  → notwendig, damit **PWA & Service Worker auf iOS funktionieren**.
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
- **iOS WLAN-Shortcut:** Öffnet direkt die WLAN-Einstellungen (`prefs:root=WIFI`). Nur auf iPhone/iPad verfügbar.
- PWA-Dateien (`index.html`, `app.js`, `style.css`, `manifest.json`, `service-worker.js`) werden über diesen AP ausgeliefert.
- **HTTPS läuft auf Port 443** mit Zertifikat (`server.crt`) und Key (`server.key`).

---

## Software

- **CircuitPython Rev. 10**
- Bibliotheken: `adafruit_requests`, `adafruit_ntp`, `adafruit_minimqtt`, `adafruit_sdcard`, `displayio` usw.
- **PWA:** lokale Bedienung und Visualisierung.
- **Service Worker:** Offline-Cache, App-installierbar.
- **Logging:** CSV- und JSON-Dateien auf SD-Karte.
- **MQTT (optional):** Veröffentlichung der Daten auf einem MQTT-Broker.

**Funktionen:**

- Shelly Toggle: Ein-/Ausschalten des Shelly Switch.
- Logging Toggle: Aktivieren/Deaktivieren der SD-Logging-Funktion.
- Echtzeitmessung: Power (W), Energy (Wh), IPs, RTC-Status, SD-Kartenstatus.
- Polling: kontinuierliches Update der Werte auf PWA.
- RTC-Synchronisation über NTP oder Shelly.
- **Fallback-Zeit, wenn keine echte Uhrzeit verfügbar** → Default: `2026-01-01`

---

## SD-Logging (überarbeitet)

Die SD-Logging-Logik nutzt eine **Queue**, um Datenverlust zu vermeiden:

- Pufferung bis zu 100 Einträgen
- Automatisches Wiederholen bei SD-Fehlern
- Neu-Mounten der SD-Karte bei Problemen
- Drop-Counter bei Queue-Überlauf
- LED-Feedback für Status

### Logging-Statuswerte:

| Wert      | Bedeutung                 |
| --------- | ------------------------- |
| `off`     | Logging deaktiviert       |
| `idle`    | Queue leer                |
| `writing` | aktueller Schreibvorgang  |
| `ok`      | letzter Write erfolgreich |
| `error`   | SD-Problem                |

Diese Statuswerte werden zusätzlich auf dem Display und in der Weboberfläche angezeigt.

---

## Service Worker & HTTPS

Damit die PWA auch auf iOS funktioniert:

- Service Worker wird unter `/service-worker.js` ausgeliefert
- korrekter MIME-Type: `application/javascript`
- **HTTPS verpflichtend**, läuft auf Port 443
- Offline-Nutzung möglich
- App-Installierbar

**Hinweis:** Browserwarnungen wegen Self-Signed Zertifikat sind normal.

---

## Installation / Deployment

1. QT-Py mit CircuitPython Rev. 10 flashen.
2. Bibliotheken in `lib/` kopieren.
3. SD-Karte einsetzen.
4. Hardware verbinden (Display, Neopixel, SD-Karte).
5. Dateien nach `/html` kopieren.
6. `secrets_shelly.py` mit WLAN-, Shelly- und optionalen MQTT-Daten erstellen.
7. **HTTPS-Zertifikat & Key speichern (`server.crt`, `server.key`)**
8. Stromversorgung anschließen.
9. Zugriff auf die PWA über AP `QT-LOGGER`: https://192.168.4.1

---

## Betrieb

- QT-Py verbindet sich automatisch zum Shelly.
- Lokaler AP `QT-LOGGER` ermöglicht Zugriff auf die PWA.
- Logging kann über die PWA ein-/ausgeschaltet werden.
- Energie- und Statusdaten werden regelmäßig aktualisiert und optional auf SD-Karte protokolliert.
- iOS Shortcut öffnet WLAN-Einstellungen direkt, um Netzwerkwechsel zu vereinfachen.
- Service Worker ermöglicht **Offline-Nutzung**.

---

## Icons / Grafiken

- Projekt-Icons (`icon-521.png`, `icon-192.png` usw.) wurden vom Projektautor erstellt unter Verwendung von KI-Hilfe (ChatGPT) und eigenen Designanweisungen.
- Keine Rechte Dritter werden verletzt. Icons dürfen im Rahmen des Projekts genutzt, veröffentlicht und verteilt werden.
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
- [ ] **HTTPS funktioniert**
- [ ] **Service Worker aktiv**
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

---

## Hinweise für Contributors

- Beiträge bitte über Pull Requests.
- Code sauber formatieren, unnötige Logs entfernen.
- Kommentare sinnvoll setzen.
- Neue Features vorher mit Maintainer absprechen.
- Lizenzhinweise und Disclaimer nicht entfernen.
- Teste alle Änderungen auf funktionierende Shelly-Kommunikation, Logging, iOS Shortcut, PWA-Auslieferung und Icons.
- **Beim Editieren des Service Workers beachten:** Nutzer müssen evtl. die PWA neu installieren.
- **HTTPS ist Voraussetzung für PWA auf iOS.**

---

## Credits

- **Adafruit:** QT-Py, Bibliotheken, Neopixel, Displays
- **Allterco Robotics:** Shelly Hardware
- **OpenAI ChatGPT:** Unterstützung bei Dokumentation, Icons und Code
