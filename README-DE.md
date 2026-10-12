# Energy-Logger

*English version: [README.md](README.md)*

Energy-Logger aus einem **Shelly Plus Plug S (Gen 2)** und einem **Adafruit QT Py
ESP32-S3** mit CircuitPython 10. Er liest Leistung und Energie vom Shelly,
schreibt sie auf eine SD-Karte, zeigt sie auf einem kleinen OLED und liefert eine
installierbare, offline-fähige Web-App (PWA) über **HTTPS** im eigenen WLAN aus.

---

## Funktionsweise

```
 Telefon ──WLAN──▶ AP Energy-Logger (192.168.4.1, HTTPS)
                        │
                 QT Py ESP32-S3 ──WLAN (Station)──▶ Shelly-AP (192.168.33.1)
                        │
                  SD-Karte · OLED · NeoPixel
```

- Der QT Py verbindet sich mit dem Access Point des Shelly und fragt alle
  `poll_interval` Sekunden `Shelly.GetStatus` ab — **nie schneller als alle 5 s**,
  sonst bekommt der Shelly Probleme.
- Gleichzeitig betreibt er einen eigenen Access Point. Das Telefon verbindet sich
  damit und öffnet `https://192.168.4.1`.
- Jeder Messwert landet in `energy_log.csv` auf der SD-Karte. Beim Monatswechsel
  wird die Datei zu `energy_log_JJJJ-MM.csv` umbenannt und eine neue begonnen.

## Hardware

| Teil | Anschluss |
|---|---|
| Adafruit QT Py ESP32-S3 (4 MB Flash, 2 MB PSRAM) | — |
| SD-Karten-Modul | SPI (SCK/MOSI/MISO), CS an **A1** |
| OLED SSD1306 128×64 **oder** SSD1327 128×128 | STEMMA QT / I²C, 0x3D oder 0x3C — wird automatisch erkannt |
| Schreibschutz-Brücke (optional) | **A0** an GND, siehe `boot.py` |
| Shelly Plus Plug S Gen 2 | im AP-Modus, Werks-IP 192.168.33.1 |

## Dateien auf dem Gerät (CIRCUITPY)

```
CIRCUITPY/
├─ code.py            Hauptprogramm
├─ boot.py            Schreibschutz-Brücke an A0
├─ safemode.py        protokolliert den Grund eines Sicherheitsmodus und startet neu
├─ config.py          Geräteeinstellungen (keine Zugangsdaten)
├─ secrets.py         WLAN-Zugangsdaten — Vorlage: secrets_example.py
├─ server.crt         TLS-Zertifikat für 192.168.4.1
├─ server.key         TLS-Schlüssel
├─ html/              die Web-App (index.html, app.js, style.css, …)
└─ lib/               Bibliotheken aus dem Adafruit-Bundle
```

`secrets.py`, `server.crt`, `server.key` und `lib/` liegen **nicht** im Repository.

### Bibliotheken

Aus dem CircuitPython-10.x-Bundle: `adafruit_httpserver`, `adafruit_requests`,
`adafruit_connection_manager`, `adafruit_sdcard`, `adafruit_bus_device`,
`adafruit_displayio_ssd1306`, `adafruit_display_text`, `asyncio`, `adafruit_ticks`,
`neopixel`, `adafruit_pixelbuf`, `adafruit_ssd1327`.

**`adafruit_sdcard`** verwenden, nicht `sdcardio` — beim Schwesterprojekt
SolarLoader brachte `sdcardio` im Feld Schreibfehler und doppelte Zeilen.

## Einrichtung

1. CircuitPython 10.x für den QT Py ESP32-S3 aufspielen.
2. `lib/`, `html/`, `code.py`, `boot.py`, `safemode.py`, `config.py` auf CIRCUITPY kopieren.
3. `secrets_example.py` nach `secrets.py` kopieren und ausfüllen.
   `ap_password` braucht 8 bis 63 Zeichen.
4. `server.crt` und `server.key` für `192.168.4.1` aufs Gerät legen. Ohne sie
   läuft der Logger per HTTP auf Port 80 — im Browser geht das, als PWA auf iOS
   lässt er sich so aber nicht installieren.
5. SD-Karte einstecken, Shelly anschließen, Strom an.
6. Am Telefon mit dem WLAN `Energy-Logger` verbinden und `https://192.168.4.1` öffnen.

Die Uhr hat weder Batterie noch Internet. Die App schickt beim Öffnen automatisch
die Uhrzeit des Telefons, solange der Logger „nicht gestellt" meldet. Hat der
Shelly selbst eine Uhrzeit, wird auch die verwendet.

## Display-Erkennung

Beim Start durchsucht der Logger den I²C-Bus (0x3D, 0x3C) und liest ein
Statusbyte vom Display. Das SSD1327 antwortet `0x02` (gemessen), das SSD1306
`0x03`/`0x43` (Datenblatt). Bei unbekanntem Byte wird SSD1306 angenommen. Das
Ergebnis steht in der BOOT-Zeile des Fehlerprotokolls und in der App unter
*Diagnose*; dort zeigt *Display testen* ein Testbild. Liegt die Erkennung einmal
daneben, lässt sich der Typ in `config.py` festlegen (`"display": "ssd1306"`,
`"ssd1327"` oder `"none"`).

## Web-App

- Aktuelle Leistung, Energie, Spannung/Strom, Steckdose ein- und ausschalten
- Zustand von SD-Karte, Protokoll und Uhr; Protokoll anhalten; Uhr von Hand stellen
- Download des Messprotokolls je Monat (in Stücken, abbrechbar)
- **Diagnose**: Softwarestand von Gerät und Oberfläche, Laufzeit, Abstürze,
  Speicher, Schleifenzeit, Serverfehler, Fehlerprotokoll, Gesundheitsspur,
  Verbindungsprotokoll des Telefons

Die App fragt den Logger alle 5 s ab, solange man hinschaut, nach 3 Minuten ohne
Berührung alle 30 s und im Hintergrund gar nicht.

## Robustheit

Aus dem SolarLoader übernommen:

- **Watchdog** (60 s) — ein hängendes Programm startet sich selbst neu
- **Absturzerkennung** im NVM, jeder Start steht in `error_log.txt`
- **`safemode.py`** schreibt den Grund eines Sicherheitsmodus auf die SD-Karte und
  startet neu (höchstens dreimal hintereinander)
- **Gesundheitsspur** `health_log.csv`: Speicher, größter Block, CPU-Temperatur,
  Schleifenzeit, langsamste Shelly-Abfrage und SD-Schreibzeit — alle 5 Minuten
- Die SD-Karte wird **automatisch neu eingebunden**, eine als gescheitert
  gemeldete Zeile wird nie doppelt geschrieben, Protokolle werden umgewälzt statt gelöscht

## Entwicklung

```bash
python3 sim/run_sim.py          # das echte code.py auf dem Mac, siehe sim/README.md
python3 sim/tests/dst.py        # schneller Einzeltest
# auf dem Gerät: tools/sd_debug.py nach CIRCUITPY, Ctrl-C, dann `import sd_debug`
python3 tools/stamp.py --check  # Version in code.py, app.js und Service Worker gleich?
python3 tools/stamp.py 2.1 "kurze Beschreibung"   # vor einer Auslieferung, dann committen
```

Code, Bezeichner und Kommentare sind Englisch, die Oberfläche ist Deutsch.

## iOS-Kurzbefehl

Der Knopf „WLAN wechseln" öffnet einen iOS-Kurzbefehl namens `ChangeWIFI`, siehe
[ChangeWIFI.md](ChangeWIFI.md).

## Lizenz

MIT, siehe [LICENSE.txt](LICENSE.txt). Shelly ist ein Produkt der Shelly Group
(vormals Allterco Robotics); dieses Projekt steht in keiner Verbindung dazu.

**Haftungsausschluss:** Nutzung auf eigenes Risiko. Der Autor übernimmt keine
Haftung für Schäden an Hardware, Software oder Sonstigem.
