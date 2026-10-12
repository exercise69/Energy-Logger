# Changelog

Alle nennenswerten Änderungen an diesem Projekt werden in dieser Datei dokumentiert.  
Das Format orientiert sich an [Keep a Changelog](https://keepachangelog.com/de/1.0.0/)  
und die Versionierung folgt [Semantic Versioning](https://semver.org/lang/de/).

---

## [2.0.0] – 2026-10-12

Überarbeitung mit den Erkenntnissen aus dem Schwesterprojekt SolarLoader.
Name jetzt durchgängig **Energy-Logger**. Code, Bezeichner und Kommentare auf
Englisch, die Oberfläche bleibt Deutsch.

### Sicherheit

- Das AP-Passwort darf keinen Vorgabewert mehr im Code haben — der alte
  Vorgabewert stand öffentlich auf GitHub. Fehlt `ap_password`, startet das
  Gerät nicht.
- `.gitignore` für Zugangsdaten, Zertifikate und Schlüssel.

### Fixed

- **Socket-Leck:** Die Antwort auf jede Shelly-Abfrage wurde nie geschlossen.
- **Uhrzeit vom Shelly:** `utc_offset` (Sekunden) wurde noch einmal mit 3600
  malgenommen. NTP konnte im Shelly-AP ohne Internet nie funktionieren.
- **SD-Karte:** Das Wiedereinbinden scheiterte an „SCK in use", weil der SPI-Bus
  bei jedem Versuch neu angelegt wurde; der CS-Pin wurde nie freigegeben.
- **`boot.py`** war leer bzw. enthielt Binärmüll (SyntaxError beim Start).
- Mehrere `SocketPool`-Objekte; nur noch einer.
- Schalten über die Web-App blockierte den Webserver bis zu 5 s.
- `debug=True` im Webserver.

### Changed

- Konfiguration getrennt: `config.py` (Einstellungen, im Repo) und `secrets.py`
  (Zugangsdaten, nicht im Repo; Vorlage `secrets_example.py`).
  `secrets_shelly.py` entfällt.
- Nur noch ein Task spricht mit dem Shelly. Abstände: Statusabfrage mindestens
  5 s nach jeder Anfrage, Befehle mindestens 1 s.
- Messprotokoll: eine CSV-Datei `energy_log.csv` mit Kopfzeile und lesbarem
  Zeitstempel, monatlich umgewälzt zu `energy_log_JJJJ-MM.csv`. Die JSONL-Datei
  entfällt.
- Uhr: Die App stellt sie beim Öffnen automatisch nach dem Telefon; sonst vom
  Shelly oder von Hand. Sommerzeit nach EU-Regel. Die gestellte Zeit geht auch
  an den Shelly.
- Web-App: neue Oberfläche mit Diagnose, Download, Anzeige veralteter Werte,
  Abfragetakt nach Sichtbarkeit (5 s / 30 s / gar nicht), Service Worker mit
  Cache-Name je Build.
- Fehlt das Zertifikat, läuft der Server per HTTP auf Port 80 statt gar nicht.

### Added (Hardwaretest 12.10.)

- Display-Erkennung: SSD1306 128×64 oder SSD1327 128×128 über das I²C-Statusbyte,
  Ergebnis in BOOT-Zeile und Diagnose, Knopf „Display testen", Typ in
  `config.py` erzwingbar.

### Fixed (Hardwaretest 12.10.)

- Der Server startete nicht („Cannot start server on None:443"): Die AP-Adresse
  ist direkt nach `start_ap()` kurz `None`. Server bindet jetzt an `0.0.0.0`.

### Removed

- MQTT (wurde nie genutzt), NTP, Default-Uhrzeit 2026-01-01.

### Added

- Watchdog (60 s), Absturzerkennung im NVM, `safemode.py`.
- `error_log.txt` (umgewälzt bei 32 KB) und Gesundheitsspur `health_log.csv`.
- Softwarestand (Version, Build) in `status.json`, auf dem Display und in der App;
  `tools/stamp.py` hält die drei Stellen gleich.
- Simulator `sim/`, der das echte `code.py` auf dem Mac ausführt, mit Tests.

---

## [1.1.0] – 2026-01-07

### Added

- **HTTPS-Unterstützung für den integrierten Webserver**
  - Zertifikats- und Key-Dateien (`server.crt`, `server.key`)
  - Server läuft nun standardmäßig auf Port `443`
  - Voraussetzung für PWA-Funktionalität (Service Worker, Installation)

- **Eigene Route für den Service Worker**
  - `/service-worker.js` wird korrekt mit MIME-Type `application/javascript` ausgeliefert
  - Stabiles Offline-Caching und PWA-Betrieb

- **Erweiterte Status-API (`/status.json`)**
  - SD-Karten-Status (inkl. Queue-Länge & Fehler)
  - Logging-Status
  - RTC-Synchronisationsstatus
  - Shelly-Status
  - MQTT-Verbindungsstatus
  - Netzwerk- und Betriebsmodusinformationen (AP/STA)

- **Verbessertes SD-Logging**
  - Write-Queue verhindert Datenverlust
  - Overflow-Erkennung mit Drop-Counter
  - Statusanzeige: `idle`, `ok`, `error`, `writing`
  - Automatisches Remounten bei Fehlern
  - LED-Feedback

- **RTC-Handling überarbeitet**
  - NTP-Synchronisation
  - Fallback-Zeit falls kein Netzwerk vorhanden
  - Optionale Synchronisation der Shelly-Zeit
  - Manueller Sync-Trigger über Web-UI

- **MQTT-Integration verbessert**
  - Optionale Nutzung
  - Fehlerrobustes Publishing
  - Verbindungsstatus wird angezeigt

### Changed

- Serverarchitektur von **HTTP → HTTPS** migriert
- JSON-Statusausgaben strukturiert und erweitert
- Debug- und Statusmeldungen vereinheitlicht
- Stabilere asynchrone Verarbeitung

### Fixed

- Service Worker wurde vorher nicht zuverlässig registriert
- PWA-Installation war in HTTP-Modus nicht möglich
- Potenzieller Datenverlust beim Loggen auf SD-Karte
- Stabilisierte Netzwerk- und Zeitinitialisierung

---

## [1.0.0] – Initial Release

### Added

- Webserver mit HTTP-Bereitstellung
- Sensor-Logging auf SD-Karte
- Web-UI
- Grundlegende API-Endpunkte
- Optionaler MQTT-Support
- Ersteinrichtung via Access-Point

