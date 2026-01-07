# Changelog

Alle nennenswerten Änderungen an diesem Projekt werden in dieser Datei dokumentiert.  
Das Format orientiert sich an [Keep a Changelog](https://keepachangelog.com/de/1.0.0/)  
und die Versionierung folgt [Semantic Versioning](https://semver.org/lang/de/).

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

