# Ausrollanleitung — Energy-Logger 2.0 (Oktober 2026)

Von Version 1.1 (Januar 2026) auf **2.0, Build 21**, dazu CircuitPython
10.0.3 → **10.1.4**. Alles mit dem USB-Kabel, der Logger hat kein Update über
das Netz.

---

## Vorher wissen

- **Das WLAN des Loggers ändert sich.** Neuer Name `Energy-Logger` statt
  `QT-LOGGER`, neues Passwort. Das alte Passwort stand als Vorgabewert öffentlich
  auf GitHub. Das neue steht in `secrets.py` im Projektordner.
- **`secrets_shelly.py` heißt jetzt `secrets.py`.** Die Datei ist schon fertig
  vorbereitet (Shelly-Zugangsdaten aus der alten Datei übernommen).
- **Das Messprotokoll hat ein neues Format.** Neue Datei `energy_log.csv` mit
  Kopfzeile und lesbarer Uhrzeit. Die alten Dateien `shelly_energy_log.csv` und
  `shelly_energy_log.jsonl` bleiben auf der Karte liegen und werden nicht mehr
  beschrieben.
- **CircuitPython wird gleich mit aktualisiert:** von 10.0.3 auf **10.1.4**.
  Das ist die Version, die beim SolarLoader auf identischer Hardware (QT Py
  ESP32-S3, 4 MB Flash, 2 MB PSRAM) im Dauerbetrieb läuft. `lib/` stammt aus dem
  10.x-Bundle und passt zu beiden Versionen.
- **Zwei Teile, nacheinander:** erst CircuitPython (Teil A) und kurz mit dem
  *alten* Programm prüfen, dann den Energy-Logger 2.0 (Teil B). So ist bei einem
  Problem klar, welcher Teil schuld ist.

## Vorbereitung

- USB-C-**Daten**kabel (kein reines Ladekabel)
- SD-Karte am besten vorher am Mac sichern (alte Protokolle)
- Die UF2-Datei für CircuitPython **10.1.4** von
  [circuitpython.org/board/adafruit_qtpy_esp32s3_4mbflash_2mbpsram](https://circuitpython.org/board/adafruit_qtpy_esp32s3_4mbflash_2mbpsram/)
  (unter „Previous Versions", Datei
  `adafruit-circuitpython-adafruit_qtpy_esp32s3_4mbflash_2mbpsram-de_DE-10.1.4.uf2`
  oder die `en_US`-Fassung — die Sprache betrifft nur Meldungen auf der seriellen
  Konsole). Sicherheitshalber auch die **10.0.3** für den Rückweg.

## Ablauf

**1. Gerät anstecken.** Das Laufwerk `CIRCUITPY` erscheint.

**2. Alten Stand sichern.** Den ganzen Inhalt von CIRCUITPY in einen Ordner auf
dem Mac kopieren, z. B. `_olderVersions/CIRCUITPY_vor_2.0/`.

### Teil A — CircuitPython 10.1.4

**A1. Bootloader starten.** Den Reset-Knopf am QT Py **zweimal kurz
hintereinander** drücken (etwa eine halbe Sekunde Abstand). Die LED leuchtet
dauerhaft, und statt `CIRCUITPY` erscheint das Laufwerk **`QTPYS3BOOT`**.

> Erscheint wieder `CIRCUITPY`: der Abstand war zu groß oder zu klein — noch
> einmal versuchen. Hat das Board einen Boot-Knopf, geht es auch so: Boot
> gedrückt halten, Reset kurz drücken, Boot loslassen.

**A2. UF2 aufspielen.** Die 10.1.4-UF2-Datei auf `QTPYS3BOOT` ziehen. Das
Laufwerk verschwindet nach einigen Sekunden von selbst (macOS meldet eventuell
„nicht korrekt ausgeworfen" — das ist hier normal), dann erscheint wieder
`CIRCUITPY`.

> Die Dateien auf CIRCUITPY bleiben dabei erhalten. Falls nicht: aus der
> Sicherung von Schritt 2 zurückkopieren.

**A3. Version prüfen.** `CIRCUITPY/boot_out.txt` öffnen. Erste Zeile:

```
Adafruit CircuitPython 10.1.4 on 2026-03-09; Adafruit QT Py ESP32-S3 4MB Flash 2MB PSRAM with ESP32S3
```

**A4. Kurz mit dem alten Programm prüfen.** Noch nichts am Programm ändern —
das alte läuft auch unter 10.1.4. Display beobachten: kommen Leistung und
Energie vom Shelly? Am Telefon mit `QT-LOGGER` verbinden und
`https://192.168.4.1` öffnen. Klappt beides, ist Teil A erledigt.

> Klappt es nicht, liegt es an CircuitPython, nicht am neuen Programm. Dann
> zurück: Schritt A1, die **10.0.3**-UF2 aufspielen — und mir die Ausgabe der
> seriellen Konsole schicken (`screen /dev/tty.usbmodem* 115200`, beenden mit
> Ctrl-A, dann K).

### Teil B — Energy-Logger 2.0

**3. Aufräumen auf CIRCUITPY.** Löschen:

```
secrets_shelly.py   (ersetzt durch secrets.py)
boot.py             (Schreibschutz-Brücke entfällt, A0 ist jetzt für eine LED reserviert)
lib/                (wird komplett neu kopiert — MQTT und NTP fallen weg)
```

`server.crt` und `server.key` bleiben liegen (gültig bis April 2028).

**4. Dateien kopieren, `code.py` zuletzt.** Aus dem Projektordner:

```
lib/            → CIRCUITPY/lib/          (ganzer Ordner, alter ist gelöscht)
html/           → CIRCUITPY/html/         (siehe Warnung unten)
config.py       → CIRCUITPY/config.py     (neu)
secrets.py      → CIRCUITPY/secrets.py    (neu)
safemode.py     → CIRCUITPY/safemode.py   (neu)
code.py         → CIRCUITPY/code.py       (zum Schluss)
```

**Ordner `sd` prüfen:** Auf CIRCUITPY muss ein leerer Ordner `sd` liegen — der
Einhängepunkt der SD-Karte. Fehlt er, im Finder neu anlegen. Ohne ihn meldet das
Gerät „folder 'sd' missing on CIRCUITPY“ und schreibt nichts.

Jede Dateiänderung startet `code.py` neu. Die letzte soll auf den vollständigen
Satz treffen, deshalb `code.py` zuletzt.

> ### ⚠️ Den Ordner `html` nicht einfach drüberziehen
>
> macOS fragt „Ersetzen?" — und *ersetzen* heißt löschen und neu anlegen.
> Hier ist das sogar erwünscht, weil sich alle Dateien geändert haben und die
> Symbole gleich bleiben. Wer sichergehen will: ⌥ beim Ziehen halten, dann bietet
> macOS „Zusammenführen" an.

**5. Auswerfen**, Kabel abziehen, Netzteil anstecken.

## Danach prüfen

**1. Display:** zeigt drei Sekunden `Energy-Logger` und `v2.0 Build 21`, danach
die Messwerte.

**2. Telefon:** altes WLAN `QT-LOGGER` vergessen, mit `Energy-Logger` verbinden
(Passwort aus `secrets.py`), `https://192.168.4.1` öffnen.

**3. Uhr:** In der Karte „Gerät" steht nach wenigen Sekunden die Uhrzeit mit
„(Telefon)". Die App stellt sie beim Öffnen selbst.

**4. Diagnose** aufklappen:
- „Software Gerät" und „Software Oberfläche" zeigen beide **Build 21**.
  Steht bei der Oberfläche eine Warnung: Seite neu laden.
- Fehlerprotokoll → „Anzeigen": oben eine Zeile
  `BOOT  v2.0 b21  reset=…  crashes=0  selfheal=0`.

**5. Nach etwa einer Minute:** „Messprotokoll" zeigt `energy_log.csv` mit
wachsender Größe.

**6. Nach fünf Minuten:** Diagnose → Gesundheitsspur → „Anzeigen" zeigt eine
erste Zeile.

## Die Web-App auf dem Home-Bildschirm

Die alte Verknüpfung zeigt auf dieselbe Adresse, der Name im Manifest hat sich
aber geändert („Energy-Logger" statt „QT-Py Shelly Logger"). Am einfachsten:
**alte Verknüpfung löschen**, in Safari `https://192.168.4.1` öffnen, Teilen →
„Zum Home-Bildschirm".

## iOS-Kurzbefehl „ChangeWIFI"

Unverändert, nichts zu tun.

## Wenn etwas klemmt

**Display bleibt schwarz oder zeigt einen Fehler, die App lädt nicht.**
Kabel anstecken, am Mac mit `screen /dev/tty.usbmodem* 115200` die Ausgabe
ansehen. Häufigster Grund: `secrets.py` fehlt oder `ap_password` ist kürzer als
8 Zeichen — das steht dann ausdrücklich in der Ausgabe.

**Zurück zum alten Stand.** Den gesicherten Ordner aus Schritt 2 vollständig
zurück auf CIRCUITPY kopieren (vorher `config.py`, `secrets.py`, `safemode.py`
löschen). Der alte Stand läuft dann wie vorher, mit dem alten WLAN. Er läuft
auch unter CircuitPython 10.1.4 — 10.0.3 zurückzuflashen (Schritt A1/A2 mit der
alten UF2) ist nur nötig, wenn schon Teil A Probleme gemacht hat. Er läuft
auch unter CircuitPython 10.1.4 — 10.0.3 zurückzuflashen (Schritt A1/A2 mit der
alten UF2) ist nur nötig, wenn schon Teil A Probleme gemacht hat.

**Die App zeigt „HTTP (ohne Zertifikat!)".** `server.crt` oder `server.key`
fehlen auf CIRCUITPY. Aus `_olderVersions/https-development/` nachkopieren.
