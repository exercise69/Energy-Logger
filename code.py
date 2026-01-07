# ================= Circuitpython version 10 =================
# ================= IMPORTS =================
import time, board, busio, digitalio, storage, adafruit_sdcard, microcontroller, rtc
import wifi, socketpool, ssl, os, json, neopixel, displayio, asyncio, gc
import traceback
try:
    from secrets_shelly import secrets
except Exception as e:
    print("secrets_shelly.py fehlt oder ist defekt:", e)
    raise

from adafruit_httpserver import Server, Request, Response, ServerStoppedError, FileResponse
from i2cdisplaybus import I2CDisplayBus
import adafruit_displayio_ssd1306
from adafruit_display_text import label
import terminalio
import adafruit_requests
import adafruit_ntp
import adafruit_minimqtt.adafruit_minimqtt as MQTT

# ================= DISPLAY =================
displayio.release_displays()
i2c = board.STEMMA_I2C()
display_bus = I2CDisplayBus(i2c, device_address=0x3D)
display = adafruit_displayio_ssd1306.SSD1306(display_bus, width=128, height=64)

splash = displayio.Group()
display.root_group = splash
color_bitmap = displayio.Bitmap(128, 64, 1)
color_palette = displayio.Palette(1)
color_palette[0] = 0x000000
bg_sprite = displayio.TileGrid(color_bitmap, pixel_shader=color_palette)
splash.append(bg_sprite)

power_label = label.Label(terminalio.FONT, text="Power: --- W", color=0xFFFFFF, x=0, y=10)
energy_label = label.Label(terminalio.FONT, text="Energy: --- Wh", color=0xFFFFFF, x=0, y=20)
shelly_status_label = label.Label(terminalio.FONT, text="Status: ---", color=0xFFFFFF, x=0, y=30)
mode_label = label.Label(terminalio.FONT, text="Modus: ---", color=0xFFFFFF, x=0, y=40)
ap_ip_label = label.Label(terminalio.FONT, text="AP IP: ---", color=0xFFFFFF, x=0, y=50)
sta_ip_label = label.Label(terminalio.FONT, text="STA IP: ---", color=0xFFFFFF, x=0, y=60)
splash.append(power_label)
splash.append(energy_label)
splash.append(shelly_status_label)
splash.append(mode_label)
splash.append(ap_ip_label)
splash.append(sta_ip_label)

# ================= LED =================
try:
    pixel = neopixel.NeoPixel(board.NEOPIXEL, 1, brightness=0.1, auto_write=False)
except:
    class DummyPixel:
        def __setitem__(self, i, c): pass
        def show(self): pass
    pixel = DummyPixel()

COLOR_OK   = (0,50,0)
COLOR_ERR  = (50,0,0)
COLOR_OFF  = (0,0,0)
_last_led = None

async def set_status_led(color):
    global _last_led
    if color != _last_led:
        pixel[0] = color
        pixel.show()
        _last_led = color

# ================= STATE =================
class Intermediate:
    def __init__(self):
        self.power = 0.0
        self.energy = 0.0
        self.shelly_status = "Init..."
        self.rtc_synced = False
        self.default_time = False
        self.ap_ip = None
        self.sta_ip = None
        self.mqtt_connected = False
        self.mqtt_client = None
        self.requests_session = None
        self.switch0 = False
        # neues Flag für Logging
        self.logging_enabled = secrets.get("logging_enabled", False)
        self.sd_status = "unmounted"
        self.sd_writing = None
        self.sd_queue_len = 0
        self.sd_queue_dropped = 0

intermediate = Intermediate()
print("status vom intermediate.logging_enabled", intermediate.logging_enabled)

# ================= REBOOT BUTTON =================
try:
    reboot_switch = digitalio.DigitalInOut(board.A0)
    reboot_switch.direction = digitalio.Direction.INPUT
    reboot_switch.pull = digitalio.Pull.UP
    _prev_switch = reboot_switch.value
    _last_switch_ts = time.monotonic()
except:
    reboot_switch = None
    _prev_switch = None
    _last_switch_ts = 0

DEBOUNCE_MS = 50

def check_reboot_switch():
    global _prev_switch, _last_switch_ts
    if reboot_switch is None:
        return
    val = reboot_switch.value
    now = time.monotonic()
    if val != _prev_switch and (now - _last_switch_ts) * 1000 > DEBOUNCE_MS:
        if not _prev_switch and val:
            microcontroller.reset()
        _prev_switch = val
        _last_switch_ts = now

# ================= SD =================
SD_PATH = "/sd"
CSV_FILE = "shelly_energy_log.csv"
JSON_FILE = "shelly_energy_log.jsonl"
sd_log_queue = []

def mount_sd(intermediate):
    try:
        cs_pin = getattr(board, secrets.get("sd_cs_pin", "A1"))
        spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
        cs = digitalio.DigitalInOut(cs_pin)
        sd = adafruit_sdcard.SDCard(spi, cs)
        storage.mount(storage.VfsFat(sd), SD_PATH)
        print("SD gemountet")
        intermediate.sd_status = "ok"
        return True
    except Exception as e:
        print("SD Fehler:", e)
        intermediate.sd_status = f"mounting SD failed {e}"
        return False

# ================= SD-LOGGING =================
MAX_QUEUE = 100

def enqueue_log(intermediate):
    # new logging_enabled logic
    if not intermediate.logging_enabled:
        return   # <<< Task beendet sich sofort

    ts = time.time()
    csv_line = f"{ts},{intermediate.power},{intermediate.energy}\n"
    json_line = json.dumps({
        "ts": ts,
        "power": intermediate.power,
        "energy": intermediate.energy
    }) + "\n"

    sd_log_queue.append((csv_line, json_line))

    # Overflow-Handling
    if len(sd_log_queue) > MAX_QUEUE:
        overflow_count = len(sd_log_queue) - MAX_QUEUE
        intermediate.sd_queue_dropped += overflow_count
        sd_log_queue[:] = sd_log_queue[overflow_count:]
        print(f"SD Log Queue voll → {overflow_count} älteste Einträge verworfen")

    # Länge IMMER aktualisieren
    intermediate.sd_queue_len = len(sd_log_queue)

    print("Enqueued SD Log:", csv_line.strip())



# ================= SD WRITER TASK ================= (newer version)
# verhindert verloren Einträge bei SD-Ausfall, started SD wiederholt neu
async def task_sd_writer(intermediate):
    
    RETRY_DELAY = 2
    IDLE_THRESHOLD = 500  # Anzahl Schleifen, bevor "idle" gesetzt wird
    idle_counter = 0
    
    while True:
        await asyncio.sleep(0.01)

        if not intermediate.logging_enabled:
            intermediate.sd_writing = "off"
            idle_counter = 0
            continue

        if not sd_log_queue:
            idle_counter += 1
            if idle_counter >= IDLE_THRESHOLD:
                intermediate.sd_writing = "idle"
            continue
        else:
            idle_counter = 0  # Queue wieder gefüllt, Counter zurücksetzen


        try:
            os.listdir(SD_PATH)
            intermediate.sd_status = "ok"
        except OSError:
            intermediate.sd_status = "SD nicht verfügbar"
            intermediate.sd_writing = "error"
            await set_status_led(COLOR_ERR)
            mount_sd(intermediate)
            await asyncio.sleep(RETRY_DELAY)
            continue

        # Wir WERDEN jetzt schreiben -> Status setzen
        intermediate.sd_writing = "writing"

        csv_line, json_line = sd_log_queue[0]

        try:
            with open(f"{SD_PATH}/{CSV_FILE}", "a") as f:
                f.write(csv_line)
                f.flush()
            with open(f"{SD_PATH}/{JSON_FILE}", "a") as f:
                f.write(json_line)
                f.flush()

            sd_log_queue.pop(0)

            intermediate.sd_writing = "ok"
            await set_status_led(COLOR_OK)

        except Exception as e:
            print("SD Log Schreibfehler:", e)
            intermediate.sd_status = "error"
            intermediate.sd_writing = "error"
            print(f"SD Fehler: {e}")
            await set_status_led(COLOR_ERR)
            await asyncio.sleep(RETRY_DELAY)



# ================= RTC =================
async def sync_rtc(intermediate):
    try:
        pool_ntp = socketpool.SocketPool(wifi.radio)
        ntp = adafruit_ntp.NTP(pool_ntp)
        rtc.RTC().datetime = ntp.datetime
        intermediate.rtc_synced = True
        print("RTC via NTP gesetzt")
        return True
    except Exception as e:
        print("NTP nicht verfügbar:", e)
        intermediate.rtc_synced = False
        default_time = time.struct_time((2026,1,1,0,0,0,-1,-1,-1))
        rtc.RTC().datetime = default_time
        print("RTC auf Default-Zeit 2026-01-01 gesetzt")
        return False

def set_rtc_from_shelly(data, intermediate):
    try:
        sys = data.get("sys", {})
        unixtime = sys.get("unixtime")
        offset = sys.get("utc_offset", 0)
        if not unixtime:
            print("Shelly liefert keine Zeit")
            return False
        rtc.RTC().datetime = time.localtime(unixtime + offset*3600)
        intermediate.rtc_synced = True
        print("RTC von Shelly gesetzt")
        return True
    except Exception as e:
        print("RTC von Shelly Fehler:", e)
        return False

def now_iso():
    t = time.localtime()
    return f"{t.tm_year:04}-{t.tm_mon:02}-{t.tm_mday:02}T{t.tm_hour:02}:{t.tm_min:02}:{t.tm_sec:02}"

# ================= MQTT =================
MQTT_ENABLED = secrets.get("mqtt_enabled", False)
MQTT_HARDWARE_SWITCH = False
MQTT_BROKER = secrets.get("mqtt_broker")
MQTT_PORT = secrets.get("mqtt_port", 1883)
MQTT_USER = secrets.get("mqtt_username")
MQTT_PASS = secrets.get("mqtt_password")
MQTT_TOPIC = secrets.get("mqtt_topic", "shelly/energy")

async def mqtt_connect(pool, intermediate):
    if not (MQTT_ENABLED and MQTT_HARDWARE_SWITCH and MQTT_BROKER):
        return
    try:
        intermediate.mqtt_client = MQTT.MQTT(
            broker=MQTT_BROKER,
            port=MQTT_PORT,
            username=MQTT_USER,
            password=MQTT_PASS,
            socket_pool=pool,
            ssl_context=ssl.create_default_context(),
        )
        intermediate.mqtt_client.connect()
        intermediate.mqtt_connected = True
    except Exception as e:
        print("MQTT Fehler:", e)

async def mqtt_publish(intermediate):
    if intermediate.mqtt_client and intermediate.mqtt_connected:
        try:
            intermediate.mqtt_client.publish(MQTT_TOPIC, json.dumps({
                "timestamp": now_iso(),
                "power_w": intermediate.power,
                "energy_wh": intermediate.energy
            }))
        except Exception as e:
            print("MQTT Publish Fehler:", e)
            intermediate.mqtt_connected = False

# ================= SHELLY =================
SHELLY_SSID = secrets["shelly_ap_ssid"]
SHELLY_PASSWORD = secrets["shelly_ap_password"]
SHELLY_IP = secrets["shelly_ip"]
SHELLY_URL = f"http://{SHELLY_IP}/rpc/Shelly.GetStatus"
POLL_INTERVAL = secrets.get("poll_interval", 10)

async def connect_sta_to_shelly(intermediate):
    print("==> Starte Verbindungs-Loop zu Shelly...")
    while True:
        try:
            if wifi.radio.connected and str(wifi.radio.ap_info.ssid) == SHELLY_SSID:
                intermediate.sta_ip = str(wifi.radio.ipv4_address)
                return True

            networks = wifi.radio.start_scanning_networks()
            found = any(net.ssid == SHELLY_SSID for net in networks)
            wifi.radio.stop_scanning_networks()

            if found:
                print(f"Shelly gefunden! Verbinde...")
                wifi.radio.connect(SHELLY_SSID, SHELLY_PASSWORD)

                for _ in range(50):
                    if wifi.radio.ipv4_address is not None:
                        intermediate.sta_ip = str(wifi.radio.ipv4_address)
                        print("STA erfolgreich verbunden:", intermediate.sta_ip)
                        return True
                    await asyncio.sleep(0.1)
            else:
                print(f"Shelly '{SHELLY_SSID}' nicht in Reichweite...")

        except Exception as e:
            print(f"STA Fehler: {e}")

        intermediate.sta_ip = None
        await asyncio.sleep(5)

async def fetch_shelly(intermediate, pool):
    if intermediate.requests_session is None:
        intermediate.requests_session = adafruit_requests.Session(pool, ssl.create_default_context())

    ntp_ok = await sync_rtc(intermediate)
    await connect_sta_to_shelly(intermediate)
    await asyncio.sleep(2)

    while True:
        if not wifi.radio.connected:
            await connect_sta_to_shelly(intermediate)

        success = False

        try:
            r = intermediate.requests_session.get(SHELLY_URL, timeout=10)
            if r.status_code == 200:
                data = r.json()
                s0 = data.get("switch:0", {})

                intermediate.power = s0.get("apower", 0.0)
                intermediate.energy = s0.get("aenergy", {}).get("total", 0.0)
                intermediate.switch0 = s0.get("output", False)
                intermediate.shelly_status = "Shelly OK"
                await set_status_led(COLOR_OK)

                enqueue_log(intermediate)
                if not ntp_ok:
                    set_rtc_from_shelly(data, intermediate)
                await mqtt_publish(intermediate)
                success = True
            else:
                intermediate.shelly_status = f"Shelly Fehler {r.status_code}"
                await set_status_led(COLOR_ERR)

        except OSError as e:
            intermediate.shelly_status = "Shelly offline"
            await set_status_led(COLOR_ERR)
            print("Shelly Fetch Fehler, retry in 5s:", e)

        await asyncio.sleep(POLL_INTERVAL if success else 5)
        gc.collect()

# ================= HTTP SERVER =================
SSID = secrets.get("ap_ssid", "QT-LOGGER")
PASSWORD = secrets.get("ap_password", "meinpasswort")

pool = socketpool.SocketPool(wifi.radio)

server = Server(
    pool, root_path="/html", https=True, certfile="server.crt", keyfile="server.key",debug=True,)
    #pool, root_path="/html", https=True, certfile="cert.pem", keyfile="key.pem",debug=True,)
# server = Server(pool, debug=False)

def start_server():
    try:
        server.stop()
    except:
        pass
    time.sleep(0.1)
    if intermediate.ap_ip:
        server.start(str(intermediate.ap_ip), 443)


# ================= 1. JSON DATA =================
# muss an erster Stelle stehen!
@server.route("/status.json")
def status_json(request: Request):
    # Vorbereitung für die Anzeige
    gc.collect()

    mode = "Offline"
    if intermediate.ap_ip and intermediate.sta_ip:
        mode = "AP+STA"
    elif intermediate.ap_ip:
        mode = "AP"
    elif intermediate.sta_ip:
        mode = "STA"

    try:
        os.listdir(SD_PATH)
        intermediate.sd_status = "ok"
    except OSError:
        intermediate.sd_status = "Nicht verfügbar"

    t = rtc.RTC().datetime
    intermediate.default_time = not intermediate.rtc_synced or t.tm_year < 2001

    # Das Daten-Objekt zusammenbauen
    data = {
        "mode": mode,
        "power": intermediate.power,
        "energy": intermediate.energy,
        "switch0": getattr(intermediate, "switch0", False),
        "shelly_status": intermediate.shelly_status,  #Shelly status
        "ap_ip": intermediate.ap_ip,
        "sta_ip": intermediate.sta_ip,
        "rtc_synced": intermediate.rtc_synced,
        "default_time": intermediate.default_time,
        "sd_status": intermediate.sd_status,
        "sd_writing": intermediate.sd_writing,
        "mqtt_enabled": MQTT_ENABLED,
        "mqtt_hw_switch": MQTT_HARDWARE_SWITCH,
        "mqtt_connected": intermediate.mqtt_connected,
        "logging_enabled": getattr(intermediate, "logging_enabled", False),
        "sd_queue_len": intermediate.sd_queue_len,
        "sd_queue_dropped": intermediate.sd_queue_dropped,
    }

    # WICHTIG: Erst in String umwandeln, dann absenden
    json_str = json.dumps(data)
    return Response(request, json_str, content_type="application/json")


# ================= 2. ROOT PATH =================
@server.route("/")
def index(request: Request):
    return FileResponse(request, "index.html", root_path="/html")


# ================= SERVICE WORKER =================
@server.route("/service-worker.js")
def sw(request: Request):
    return FileResponse(
        request,
        "service-worker.js",  # Datei liegt im /html-Ordner
        root_path="/html",
        content_type="application/javascript"  # wichtig!
    )


# ================= 3. STATIC FILES =================
@server.route("/html/<filename>")
def static_file(request: Request, filename: str):
    return FileResponse(request, filename, root_path="/html")


# ================= 4. FALLBACK =================
@server.route("/<filename>")
def static_file_root(request: Request, filename: str):
    return FileResponse(request, filename, root_path="/html")


# ================= SET SHELLY TIME =================
async def set_shelly_time_async(unixtime, intermediate):
    try:
        shelly_url = f"http://{SHELLY_IP}/rpc/Sys.SetTime?unixtime={unixtime}"
        if intermediate.requests_session is None:
            intermediate.requests_session = adafruit_requests.Session(pool, ssl.create_default_context())
        r = intermediate.requests_session.get(shelly_url, timeout=5)
        if r.status_code == 200:
            print(f"[Async] Shelly Zeit erfolgreich gesetzt: {unixtime}")
        else:
            print(f"[Async] Shelly Fehler {r.status_code}")
    except Exception as e:
        print("[Async] Fehler beim Setzen der Shelly-Zeit:", e)
    finally:
        gc.collect()

@server.route("/set_shelly_time", methods=["POST"])
def set_time(request: Request):
    gc.collect()
    try:
        raw_dt = request.form_data.get("dt")
        if not raw_dt:
            return Response(request, "Keine Daten gesendet", status=400)
        raw_dt = raw_dt.replace("%3A", ":")
        if "T" not in raw_dt:
            return Response(request, "Ungültiges Format", status=400)
        date_part, time_part = raw_dt.split("T")
        try:
            y, m, d = map(int, date_part.split("-"))
            hh, mm = map(int, time_part.split(":"))
        except Exception:
            return Response(request, "Ungültige Datumsangaben", status=400)
        new_tm = time.struct_time((y, m, d, hh, mm, 0, 0, -1, -1))
        rtc.RTC().datetime = new_tm
        intermediate.rtc_synced = True
        unixtime = int(time.mktime(new_tm))
        if unixtime < 0:
            return Response(request, "Ungültige Zeit (vor 1970)", status=400)
        asyncio.create_task(set_shelly_time_async(unixtime, intermediate))
        return Response(request, "OK")
    except Exception as e:
        print("Fehler set_time:", e)
        return Response(request, f"Fehler: {e}", status=500)
    finally:
        gc.collect()


# ================= TOGGLE SHELLY =================
@server.route("/toggle_shelly", methods=["POST"])
def toggle_shelly(request: Request):
    try:
        url = f"http://{SHELLY_IP}/rpc/Switch.Toggle?id=0"
        # print("DEBUG: Shelly URL:", url)

        # Session anlegen, falls noch nicht vorhanden
        if intermediate.requests_session is None:
            intermediate.requests_session = adafruit_requests.Session(
                socketpool.SocketPool(wifi.radio),
                ssl.create_default_context()
            )

        # Shelly Toggle senden und Response sauber schließen
        with intermediate.requests_session.get(url, timeout=5) as r:
            # print("DEBUG: Shelly Response Code:", r.status_code)
            if r.status_code == 200:
                # Status im Intermediate direkt aktualisieren, falls möglich
                intermediate.switch0 = not intermediate.switch0
                return Response(request, "OK")
            else:
                return Response(request, f"Fehler Shelly {r.status_code}", status=500)

    except Exception as e:
        print("Fehler toggle_shelly:", e)
        return Response(request, f"Fehler: {e}", status=500)

    finally:
        gc.collect()


# ================= TOGGLE LOGGING =================
@server.route("/toggle_logging", methods=["POST"])
def toggle_logging(request: Request):
    try:
        # Logging-Flag umschalten
        intermediate.logging_enabled = not getattr(intermediate, "logging_enabled", False)
        status_text = "aktiviert" if intermediate.logging_enabled else "deaktiviert"
        print(f"Logging {status_text}")

        return Response(request, f"Logging {status_text}")

    except Exception as e:
        print("Fehler toggle_logging:", e)
        return Response(request, f"Fehler: {e}", status=500)

    finally:
        gc.collect()


# ================= TASKS =================
async def task_reboot_switch():
    while True:
        check_reboot_switch()
        await asyncio.sleep(0.05)

async def task_display():
    while True:
        mode = "Offline"
        if intermediate.ap_ip and intermediate.sta_ip:
            mode = "AP+STA"
        elif intermediate.ap_ip:
            mode = "AP"
        elif intermediate.sta_ip:
            mode = "STA"

        power_label.text = f"Power: {intermediate.power:.1f} W"
        energy_label.text = f"Energy: {intermediate.energy:.1f} Wh"
        shelly_status_label.text = f"{intermediate.shelly_status}"
        mode_label.text = f"Modus: {mode}"
        ap_ip_label.text = f"AP IP: {intermediate.ap_ip or '-'}"
        sta_ip_label.text = f"STA IP: {intermediate.sta_ip or '-'}"

        await asyncio.sleep(0.5)


# ================= SERVER POLL (updated) =================
async def task_server():
    while True:
        try:
            # Hauptserver-Polling
            server.poll()

        # ===== Bekanntes Szenario: Server gestoppt =====
        except ServerStoppedError:
            print("Server stopped → restarting…")
            start_server()

        # ===== Netzwerk-/Socketfehler =====
        except OSError as e:
            print("WiFi/Socket error in server.poll():", e)
            # Optional: Server neu starten
            start_server()

        # ===== RuntimeError von CircuitPython/WiFi =====
        except RuntimeError as e:
            print("RuntimeError in server.poll():", e)
            start_server()

        # ===== Speicherprobleme =====
        except MemoryError as e:
            print("MemoryError → rebooting:", e)
            microcontroller.reset()  # ESP32-S3 sofort neu starten

        # ===== Unerwartete Fehler =====
        except Exception as e:
            print("UNEXPECTED server error:", e)
            try:
                traceback.print_exception(e)
            except Exception:
                # Falls traceback Probleme macht
                print(repr(e))
            # Task läuft weiter

        finally:
            gc.collect()
            # Garantiertes Sleep, um Event-Loop nicht zu blockieren
            await asyncio.sleep(0.05)


# ================= MAIN =================
async def main():
    gc.collect()

    mount_sd(intermediate)

    wifi.radio.stop_ap()
    await asyncio.sleep(0.5)

    wifi.radio.start_ap(ssid=SSID, password=PASSWORD)
    await asyncio.sleep(2)

    intermediate.ap_ip = str(wifi.radio.ipv4_address_ap)
    print("AP aktiv:", intermediate.ap_ip)

    start_server()

    tasks = [
        fetch_shelly(intermediate, pool),
        task_reboot_switch(),
        task_display(),
        task_server(),
        task_sd_writer(intermediate)
    ]

    await asyncio.gather(*tasks)

asyncio.run(main())

