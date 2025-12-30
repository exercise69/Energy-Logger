const offlineBanner = document.getElementById("offlineBanner");
const toggleBtn = document.getElementById("toggleShelly");
const shellyStatus = document.getElementById("shelly_status");
const timeForm = document.getElementById("timeForm");
const responseMsg = document.getElementById("timeResponse");

// Logging
const toggleLoggingBtn = document.getElementById("toggleLogging");
const loggingStatus = document.getElementById("logging_status");

// WLAN wechseln
const wifiBtn = document.getElementById("wifiBtn");
wifiBtn.addEventListener("click", openWifi);
function openWifi() {
  if (/iPhone|iPad|iPod/i.test(navigator.userAgent)) {
    wifiBtn.disabled = true;
    window.location.href = "shortcuts://run-shortcut?name=ChangeWIFI";
    setTimeout(() => { wifiBtn.disabled = false; }, 2000);
  } else {
    alert("WLAN-Wechsel nur auf iPhone/iPad verfügbar.");
  }
}

// Shelly Toggle Button
function updateShellyButton(isOn) {
  shellyStatus.textContent = isOn ? "Ein" : "Aus";
  toggleBtn.textContent = isOn ? "Ausschalten" : "Einschalten";
}

// Logging Button
function updateLoggingButton(isEnabled) {
  loggingStatus.textContent = isEnabled ? "Aktiv" : "Inaktiv";
  toggleLoggingBtn.textContent = isEnabled ? "Logging deaktivieren" : "Logging aktivieren";
}

// fetch mit Timeout
async function fetchWithTimeout(url, timeout = 3000) {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeout);
  try {
    const resp = await fetch(url, { signal: controller.signal, cache: "no-store" });
    clearTimeout(id);
    return resp;
  } catch (err) {
    clearTimeout(id);
    throw err;
  }
}

// Banner setzen
function setBannerOnline() {
  offlineBanner.querySelector("span").innerHTML = "Online<br>verbunden";
  offlineBanner.style.background = "#4caf50";
  wifiBtn.disabled = false;
  toggleBtn.disabled = false;
  toggleLoggingBtn.disabled = false;
}

function setBannerOffline() {
  offlineBanner.querySelector("span").innerHTML = "Offline<br>WLAN prüfen";
  offlineBanner.style.background = "#900";
  wifiBtn.disabled = false;
  toggleBtn.disabled = true;
  toggleLoggingBtn.disabled = true;
}

// Shelly Daten abrufen
async function updateData() {
  if (!navigator.onLine) {
    setBannerOffline();
    return;
  }

  try {
    const resp = await fetchWithTimeout("/status.json", 3000);
    if (!resp.ok) throw new Error("Netzwerkfehler");
    const data = await resp.json();

    setBannerOnline();

    document.getElementById("mode").textContent = data.mode;
    document.getElementById("power").textContent = data.power.toFixed(1) + " W";
    document.getElementById("energy").textContent = data.energy.toFixed(1) + " Wh";
    document.getElementById("status").textContent = data.status;
    document.getElementById("ap_ip").textContent = data.ap_ip;
    document.getElementById("sta_ip").textContent = data.sta_ip || "Nicht verbunden";
    document.getElementById("rtc_synced").textContent = data.rtc_synced ? "Ja" : "Nein";
    document.getElementById("rtc_default").textContent = data.default_time ? "Ja (Default 2026-01-01)" : "Nein";
    document.getElementById("sd_status").textContent = data.sd_status;
    document.getElementById("mqtt_enabled").textContent = data.mqtt_enabled ? "Aktiv" : "Aus";
    document.getElementById("mqtt_hw_switch").textContent = data.mqtt_hw_switch ? "An" : "Aus";
    document.getElementById("mqtt_connected").textContent = data.mqtt_connected ? "Verbunden" : "Getrennt";

    updateShellyButton(data.switch0);
    updateLoggingButton(data.logging_enabled);

  } catch (e) {
    console.log("Fehler beim Abrufen der Daten:", e);
    setBannerOffline();
  }
}

// Zeit senden
timeForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  responseMsg.textContent = "Übertragung läuft…";
  try {
    const formData = new URLSearchParams();
    formData.append("dt", document.getElementById("dt").value);
    const r = await fetch("/set_shelly_time", { method: "POST", body: formData });
    if (!r.ok) throw new Error();
    responseMsg.textContent = "✓ Zeit gesetzt!";
    responseMsg.className = "status-ok";
  } catch {
    responseMsg.textContent = "❌ Fehler";
    responseMsg.className = "status-err";
  }
});

// Polling bis stabil
async function pollUntilStable(checkFunc, interval = 200, maxAttempts = 10) {
  let lastValue;
  for (let i = 0; i < maxAttempts; i++) {
    const currentValue = await checkFunc();
    if (lastValue !== undefined && currentValue === lastValue) {
      return currentValue; // stabiler Zustand erreicht
    }
    lastValue = currentValue;
    await new Promise(r => setTimeout(r, interval));
  }
  return lastValue; // nach maxAttempts zurückgeben
}

// Toggle Shelly
toggleBtn.addEventListener("click", async () => {
  if (!navigator.onLine) { alert("Offline: Shelly nicht erreichbar!"); return; }

  toggleBtn.disabled = true;
  try {
    await fetch("/toggle_shelly", { method: "POST" });

    await pollUntilStable(async () => {
      const resp = await fetchWithTimeout("/status.json");
      const data = await resp.json();
      updateShellyButton(data.switch0);
      return data.switch0;
    });

  } catch {
    alert("Fehler: Shelly nicht erreichbar!");
  } finally {
    toggleBtn.disabled = false;
    toggleBtn.blur();
  }
});

// Toggle Logging
toggleLoggingBtn.addEventListener("click", async () => {
  if (!navigator.onLine) { alert("Offline: Logging nicht erreichbar!"); return; }

  toggleLoggingBtn.disabled = true;
  try {
    await fetch("/toggle_logging", { method: "POST" });

    await pollUntilStable(async () => {
      const resp = await fetchWithTimeout("/status.json");
      const data = await resp.json();
      updateLoggingButton(data.logging_enabled);
      return data.logging_enabled;
    });

  } catch {
    alert("Fehler beim Umschalten des Logging");
  } finally {
    toggleLoggingBtn.disabled = false;
    toggleLoggingBtn.blur();
  }
});

// Updates und Events
window.updateInterval = setInterval(updateData, 5000);
window.addEventListener("load", updateData);
window.addEventListener("online", updateData);
window.addEventListener("offline", setBannerOffline);

// Service Worker
if ("serviceWorker" in navigator) {
  navigator.serviceWorker
    .register("/html/service-worker.js")
    .then(() => console.log("SW registriert"))
    .catch(err => console.log("SW Fehler:", err));
}
