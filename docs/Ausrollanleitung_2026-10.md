# Ausrollanleitung — Energy-Logger 2.0 (Oktober 2026)

Von Version 1.1 (Januar 2026) auf **2.0, Build 16**. Alles mit dem USB-Kabel,
der Logger hat kein Update über das Netz.

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
- **CircuitPython:** 10.0.3 läuft weiter. Empfohlen ist trotzdem das aktuelle
  10.x — `lib/` stammt aus dem Bundle vom 20.05.2026 für 10.x.

## Vorbereitung

- USB-C-**Daten**kabel (kein reines Ladekabel)
- SD-Karte am besten vorher am Mac sichern (alte Protokolle)

## Ablauf

**1. Gerät anstecken.** Das Laufwerk `CIRCUITPY` erscheint.

> Erscheint es nur schreibgeschützt: die Brücke A0–GND entfernen. Mit Brücke
> darf nur das Programm schreiben, nicht der Mac (siehe `boot.py`).

**2. Alten Stand sichern.** Den ganzen Inhalt von CIRCUITPY in einen Ordner auf
dem Mac kopieren, z. B. `_olderVersions/CIRCUITPY_vor_2.0/`.

**3. Aufräumen auf CIRCUITPY.** Löschen:

```
secrets_shelly.py   (ersetzt durch secrets.py)
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
boot.py         → CIRCUITPY/boot.py
code.py         → CIRCUITPY/code.py       (zum Schluss)
```

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

**1. Display:** zeigt drei Sekunden `Energy-Logger` und `v2.0 Build 16`, danach
die Messwerte.

**2. Telefon:** altes WLAN `QT-LOGGER` vergessen, mit `Energy-Logger` verbinden
(Passwort aus `secrets.py`), `https://192.168.4.1` öffnen.

**3. Uhr:** In der Karte „Gerät" steht nach wenigen Sekunden die Uhrzeit mit
„(Telefon)". Die App stellt sie beim Öffnen selbst.

**4. Diagnose** aufklappen:
- „Software Gerät" und „Software Oberfläche" zeigen beide **Build 16**.
  Steht bei der Oberfläche eine Warnung: Seite neu laden.
- Fehlerprotokoll → „Anzeigen": oben eine Zeile
  `BOOT  v2.0 b16  reset=…  crashes=0  selfheal=0`.

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
löschen). Der alte Stand läuft dann wie vorher, mit dem alten WLAN.

**Die App zeigt „HTTP (ohne Zertifikat!)".** `server.crt` oder `server.key`
fehlen auf CIRCUITPY. Aus `_olderVersions/https-development/` nachkopieren.
