const offlineBanner = document.getElementById("offlineBanner");
const toggleBtn = document.getElementById("toggleShelly");
const timeForm = document.getElementById("timeForm");
const responseMsg = document.getElementById("timeResponse");
const toggleLoggingBtn = document.getElementById("toggleLogging");

// Use classes for shelly_status and logging_status
function setShellyStatus(text) {
  document.querySelectorAll(".shelly_status")
    .forEach(el => el.textContent = text);
}

function setLoggingStatus(text) {
  document.querySelectorAll(".logging_status")
    .forEach(el => el.textContent = text);
}


/**
 * Setzt die Status-Anzeige eines Indikators
 *
 * @param {string} id     -> z.B. "power_indicator"
 * @param {string} state  -> "running" | "disabled" | "error"
 */
function setIndicator(id, state) {
  const el = document.getElementById(id);
  if (!el) return;

  // alle Klassen zurücksetzen
  el.className = "indicator";
  // nur bestimmte Klassen zurücksetzen
  // el.classList.remove("running", "error", "disabled");

  // Neue Klasse setzen
  if (state === "running") el.classList.add("running");
  else if (state === "error") el.classList.add("error");
  else if (state === "writing") el.classList.add("writing");
  else if (state === "idle") el.classList.add("idle");
  else if (state === "ok") el.classList.add("ok");
  else el.classList.add("disabled");
}

/**
 * Beispielhafte Demo-Werte
 * (später ersetzt du das durch echte API-Daten)
 */
function setIndicatorsDisabled() {
  setIndicator("power_indicator", "disabled");
  setIndicator("energy_indicator", "disabled");
  setIndicator("status_indicator", "disabled");
  setIndicator("ap_ip_indicator", "disabled");
  setIndicator("sta_ip_indicator", "disabled");
  setIndicator("rtc_synced_indicator", "disabled");
  setIndicator("rtc_default_indicator", "disabled");
  setIndicator("sd_status_indicator", "disabled");
  setIndicator("logging_status_indicator", "disabled");
  setIndicator("sd_writing_indicator", "disabled");
  setIndicator("sd_queue_len_indicator", "disabled");
  setIndicator("sd_queue_dropped_indicator", "disabled");
  setIndicator("mqtt_enabled_indicator", "disabled");
  setIndicator("mqtt_hw_switch_indicator", "disabled");
  setIndicator("mqtt_connected_indicator", "disabled");
}

// --- Indicator initialisieren ---
document.addEventListener("DOMContentLoaded", setIndicatorsDisabled);

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
  setShellyStatus(isOn ? "ein" : "aus");
  toggleBtn.textContent = isOn ? "Ausschalten" : "Einschalten";
}

// Logging Button
function updateLoggingButton(isEnabled) {
  setLoggingStatus(isEnabled ? "aktiv" : "inaktiv");
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
    setIndicatorsDisabled();
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
    setShellyStatus(data.shelly_status);
    document.getElementById("ap_ip").textContent = data.ap_ip;
    document.getElementById("sta_ip").textContent = data.sta_ip || "Nicht verbunden";
    document.getElementById("rtc_synced").textContent = data.rtc_synced ? "Ja" : "Nein";
    document.getElementById("rtc_default").textContent = data.default_time ? "Default 2026-01-01" : "Nein";
    document.getElementById("sd_status").textContent = data.sd_status;
    document.getElementById("sd_writing").textContent = data.sd_writing;
    document.getElementById("sd_queue_len").textContent = data.sd_queue_len;
    document.getElementById("sd_queue_dropped").textContent = data.sd_queue_dropped;
    document.getElementById("mqtt_enabled").textContent = data.mqtt_enabled ? "Aktiv" : "Aus";
    document.getElementById("mqtt_hw_switch").textContent = data.mqtt_hw_switch ? "An" : "Aus";
    document.getElementById("mqtt_connected").textContent = data.mqtt_connected ? "Verbunden" : "Getrennt";

    updateShellyButton(data.switch0);
    updateLoggingButton(data.logging_enabled);

    // Indikatoren aktualisieren
    updateIndicators(data);

  } catch (e) {
    console.log("Fehler beim Abrufen der Daten:", e);
    setBannerOffline();
  }
}


// Indikatoren aktualisieren
function updateIndicators(data) {
  setIndicator("power_indicator", data.power > 0 ? "running" : "disabled");
  setIndicator("energy_indicator", data.power > 0 ? "running" : "disabled"); // gleicher Zustand wie Power

  setIndicator("status_indicator", data.shelly_status === "error" ? "error" : "running");
  setIndicator("ap_ip_indicator", isIp(data.ap_ip) ? "running" : "error");
  setIndicator("sta_ip_indicator", isIp(data.sta_ip) ? "running" : "error");

  setIndicator("rtc_synced_indicator", data.rtc_synced ? "running" : "disabled");
  setIndicator("rtc_default_indicator", data.default_time ? "running" : "disabled"); 

  setIndicator("sd_status_indicator", data.sd_status === "ok" ? "running" : "error")

  setIndicator("logging_status_indicator",data.logging_enabled === true ? "running" : "disabled");
  
  if (data.sd_writing === "off") { 
    setIndicator("sd_writing_indicator", "off");
  } else if (data.sd_writing === "writing") {
    setIndicator("sd_writing_indicator", "writing");
  } else if (data.sd_writing === "idle") {
    setIndicator("sd_writing_indicator", "idle");
  } else if (data.sd_writing === "ok") {
    setIndicator("sd_writing_indicator", "ok");
  } else if (data.sd_writing === "error") {
    setIndicator("sd_writing_indicator", "error");
  } else {
    setIndicator("sd_writing_indicator", "disabled");
  }

  // Queue Indikatoren
  setIndicator("sd_queue_len_indicator", 
      data.sd_queue_len === 0 ? "running" :
      data.sd_queue_len < 5 ? "idle" : "error");

  setIndicator("sd_queue_dropped_indicator", 
      data.sd_queue_dropped === 0 ? "running" :
      data.sd_queue_dropped < 3 ? "idle" : "error");


  setIndicator("mqtt_enabled_indicator", data.mqtt_enabled ? "running" : "disabled");
  setIndicator("mqtt_hw_switch_indicator", data.mqtt_hw_switch ? "running" : "disabled");
  setIndicator("mqtt_connected_indicator", data.mqtt_connected ? "running" : "disabled");    
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
    .register("/service-worker.js")
    .then(() => console.log("SW registriert"))
    .catch(err => console.log("SW Fehler:", err));

  // Auf Nachrichten vom SW hören (neu!)
  navigator.serviceWorker.addEventListener('message', event => {
    if (event.data.type === 'SERVER_STATUS' && event.data.online) {
      console.log("Server wieder online – Seite reload");
      location.reload();
    }
  });
}

function isIp(str) {
  return typeof str === "string" && /^(25[0-5]|2[0-4]\d|1?\d?\d)(\.(25[0-5]|2[0-4]\d|1?\d?\d)){3}$/.test(str);
}
