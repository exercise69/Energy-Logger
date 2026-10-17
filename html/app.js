// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Uwe Piro — https://github.com/exercise69/Energy-Logger
//
// Code and comments in English, user-facing text in German.

// UI software version. Set by tools/stamp.py, not by hand.
const UI_VERSION = '2.0';
const UI_BUILD   = 22;
const UI_DATE    = '2026-10-17';

const $ = (id) => document.getElementById(id);

function setText(id, text) {
  const el = $(id);
  if (el && el.textContent !== String(text)) el.textContent = text;
}

function setIndicator(id, state) {
  const el = $(id);
  if (el) el.className = 'indicator ' + (state || 'disabled');
}

function duration(s) {
  return s < 90 ? Math.round(s) + ' s' : s < 5400 ? Math.round(s / 60) + ' min'
       : (s / 3600).toFixed(1) + ' h';
}

function formatBytes(n) {
  return n < 1024 ? n + ' B' : n < 1048576 ? (n / 1024).toFixed(1) + ' KB'
       : (n / 1048576).toFixed(2) + ' MB';
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function fetchWithTimeout(url, options = {}, timeout = 8000) {
  const ctrl = new AbortController();
  const id = setTimeout(() => ctrl.abort(), timeout);
  try {
    return await fetch(url, { ...options, signal: ctrl.signal, cache: 'no-store' });
  } finally {
    clearTimeout(id);
  }
}

function post(url, body) {
  return fetchWithTimeout(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: body || '',
  });
}

// Device status codes -> German labels
const LABELS = {
  shelly: { starting: 'Start…', searching: 'suche Shelly-WLAN', ok: 'verbunden',
            offline: 'nicht erreichbar' },
  timeSource: { phone: 'Telefon', manual: 'von Hand', shelly: 'Shelly' },
  sd: { ok: 'ok', error: 'Fehler', unmounted: 'nicht eingebunden' },
  writing: { idle: 'wartet', writing: 'schreibt', ok: 'geschrieben', error: 'Fehler',
             retry: 'neuer Versuch', off: 'aus' },
};
const label = (group, code) => (LABELS[group] && LABELS[group][code]) || code;

// ===== POLLING =====
// The app polls the logger, not the Shelly — the logger polls the Shelly
// itself, never faster than every 5 s (poll_interval in config.py). Still,
// every request here costs a TLS handshake on the ESP32, so:
//   page in background         -> no polling at all
//   visible, recently touched  -> every 5 s
//   visible, untouched 3 min   -> every 30 s
const POLL_ACTIVE = 5000;
const POLL_IDLE   = 30000;
const IDLE_AFTER  = 180000;

let _lastActivity = Date.now();
let _pollOn = false;
let _pollTimer = null;

function schedulePoll() {
  _pollTimer = null;
  if (!_pollOn || document.hidden) return;
  const ms = Date.now() - _lastActivity < IDLE_AFTER ? POLL_ACTIVE : POLL_IDLE;
  _pollTimer = setTimeout(() => { updateData().finally(schedulePoll); }, ms);
}

function pollNow() {
  if (_pollTimer) { clearTimeout(_pollTimer); _pollTimer = null; }
  if (!_pollOn || document.hidden) return;
  updateData().finally(schedulePoll);
}

function startPolling() { _pollOn = true; if (!_pollTimer) pollNow(); }
function stopPolling() {
  _pollOn = false;
  if (_pollTimer) { clearTimeout(_pollTimer); _pollTimer = null; }
}

['pointerdown', 'keydown', 'touchstart', 'scroll', 'wheel'].forEach(ev =>
  document.addEventListener(ev, () => {
    const wasIdle = Date.now() - _lastActivity >= IDLE_AFTER;
    _lastActivity = Date.now();
    if (wasIdle) pollNow();
  }, { passive: true, capture: true }));

document.addEventListener('visibilitychange', () => {
  if (document.hidden) {
    if (_pollTimer) { clearTimeout(_pollTimer); _pollTimer = null; }
  } else {
    _lastActivity = Date.now();
    pollNow();
  }
});

// ===== BANNER =====
const STALE_S = 30;
let _lastSuccess = 0;

function banner(text, color, online) {
  setText('bannerText', text);
  $('offlineBanner').style.background = color;
  $('toggleShelly').disabled = !online;
  $('toggleLogging').disabled = !online;
}

// Age of the values. Without this, frozen values looked like current ones.
setInterval(() => {
  if (!_lastSuccess || document.hidden) return;
  showConnection();
  const age = (Date.now() - _lastSuccess) / 1000;
  if (age >= STALE_S) {
    banner('Werte von ' + new Date(_lastSuccess).toLocaleTimeString('de') +
           ' — vor ' + duration(age), '#7a5500', false);
  }
}, 5000);

// ===== CONNECTION LOG (this phone) =====
// What gets lost on the way only the phone sees. It keeps the last failures
// itself; they are shown under Diagnose.
const CONN_KEY = 'el_connection';
const CONN_MAX = 40;
let _requests = 0, _failedTotal = 0, _failStreak = 0, _streakSince = 0;

function connRead() {
  try { return JSON.parse(localStorage.getItem(CONN_KEY)) || []; }
  catch (e) { return []; }
}

function connNote(kind, info) {
  const l = connRead();
  l.push({ t: Date.now(), kind: kind, info: info || '' });
  while (l.length > CONN_MAX) l.shift();
  try { localStorage.setItem(CONN_KEY, JSON.stringify(l)); } catch (e) {}
  showConnection();
}

function showConnection() {
  const l = connRead().slice().reverse();
  setText('conn_log', l.length ? l.map(x => {
    const d = new Date(x.t);
    return d.toLocaleDateString('de', { day: '2-digit', month: '2-digit' }) + ' ' +
           d.toLocaleTimeString('de') + '  ' + x.kind + (x.info ? '  (' + x.info + ')' : '');
  }).join('\n') : 'keine Störungen notiert');
  setText('conn_last', _lastSuccess
    ? new Date(_lastSuccess).toLocaleTimeString('de') + ' — vor ' +
      duration((Date.now() - _lastSuccess) / 1000)
    : 'noch keine');
  setText('conn_count', _requests + ' Abfragen, ' + _failedTotal + ' fehlgeschlagen');
}

function errorText(e, phase) {
  if (e && e.name === 'AbortError')
    return phase === 'connect' ? 'Zeitüberschreitung — keine Antwort'
                               : 'Zeitüberschreitung — Antwort abgerissen';
  if (e instanceof SyntaxError) return 'Antwort unvollständig';
  if (e && /^HTTP /.test(e.message)) return 'Gerät meldet ' + e.message;
  if (e instanceof TypeError) return 'Gerät nicht erreichbar';
  return (e && e.name || 'Fehler') + ': ' + (e && e.message || '');
}

// ===== STATUS =====
// The timeout covers the whole request including reading the body — if the
// response breaks off midway, res.json() would otherwise wait forever and the
// app freezes. A request that still hangs is skipped after HANG_MS.
const STATUS_TIMEOUT = 8000;
const HANG_MS = 20000;
let _running = false, _runningSince = 0, _seq = 0;
let _timeSent = false;

async function updateData() {
  if (_running && Date.now() - _runningSince < HANG_MS) return;
  const seq = ++_seq;
  _running = true;
  _runningSince = Date.now();
  _requests++;
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), STATUS_TIMEOUT);
  let phase = 'connect';
  try {
    const res = await fetch('status.json', { signal: ctrl.signal, cache: 'no-store' });
    phase = 'body';
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const d = await res.json();
    if (seq !== _seq) return;
    if (_failStreak > 0)
      connNote('wieder da', 'nach ' + _failStreak + ' Fehlern, ' +
               duration((Date.now() - _streakSince) / 1000));
    _failStreak = 0;
    _lastSuccess = Date.now();
    banner('Online — ' + new Date().toLocaleTimeString('de'), '#2e7d32', true);
    showStatus(d);
    if (!d.rtc_synced && !_timeSent) sendPhoneTime();
  } catch (e) {
    if (seq !== _seq) return;
    if (_failStreak === 0) _streakSince = Date.now();
    _failStreak++;
    _failedTotal++;
    if (_failStreak <= 3) connNote(errorText(e, phase));
    if (!_lastSuccess) banner('Keine Verbindung — WLAN prüfen', '#900', false);
  } finally {
    clearTimeout(timer);
    if (seq === _seq) _running = false;
  }
}

function showStatus(d) {
  setText('power', d.power.toFixed(1));
  setText('energy', (d.energy / 1000).toFixed(3) + ' kWh');
  setIndicator('energy_indicator', d.shelly_ok ? (d.power > 0.5 ? 'running' : 'idle') : 'disabled');

  const age = d.shelly_age_s == null ? '' : ' (vor ' + duration(d.shelly_age_s) + ')';
  setText('shelly_status', label('shelly', d.shelly_state) + age);
  setIndicator('shelly_indicator', d.shelly_ok ? 'ok' : 'error');
  setText('volt_amp', d.voltage == null ? '--'
          : d.voltage.toFixed(0) + ' V / ' + (d.current || 0).toFixed(2) + ' A');
  setText('shelly_temp', d.shelly_temp == null ? '--' : d.shelly_temp.toFixed(1) + ' °C');
  setText('output', d.output ? 'ein' : 'aus');
  setText('toggleShelly', d.output ? 'Ausschalten' : 'Einschalten');

  setText('clock', d.rtc_synced ? d.time + ' (' + label('timeSource', d.time_source) + ')'
                                : 'nicht gestellt');
  setIndicator('rtc_indicator', d.rtc_synced ? 'ok' : 'error');
  setText('sd_status', label('sd', d.sd_status) + ' · ' + label('writing', d.sd_writing) +
          (d.sd_log_size ? ' · ' + formatBytes(d.sd_log_size) : ''));
  setIndicator('sd_indicator', d.sd_status === 'ok' ? 'ok' : 'error');
  setText('logging_status', d.logging_enabled ? 'aktiv' : 'aus');
  setIndicator('logging_indicator', d.logging_enabled ? 'running' : 'off');
  setText('toggleLogging', d.logging_enabled ? 'Protokoll anhalten' : 'Protokoll starten');
  setText('queue', d.sd_queue_len + ' / ' + d.sd_queue_dropped);
  setIndicator('queue_indicator', d.sd_queue_dropped > 0 ? 'error'
               : d.sd_queue_len > 5 ? 'idle' : 'ok');
  setText('network', (d.https ? 'HTTPS' : 'HTTP (ohne Zertifikat!)') + ' · AP ' + d.ap_ssid +
          ' ' + (d.ap_ip || '-') + ' · Shelly ' + (d.sta_ip || 'nicht verbunden'));

  // Diagnostics
  setText('d_version', d.version + ' · Build ' + d.build + ' · ' + d.date);
  setText('d_ui_version', UI_VERSION + ' · Build ' + UI_BUILD + ' · ' + UI_DATE +
          (d.build !== UI_BUILD ? '  ⚠ passt nicht zum Gerät — Seite neu laden' : ''));
  setText('d_uptime', duration(d.uptime_h * 3600));
  setText('d_crashes', d.crash_count);
  setText('d_mem', d.mem_free ? formatBytes(d.mem_free) + ' / ' + formatBytes(d.mem_block)
                              : 'nach der ersten Messung (5 min)');
  setText('d_cpu', d.cpu_temp ? d.cpu_temp.toFixed(1) + ' °C' : '--');
  const DISPLAY_NAMES = { ssd1306: 'SSD1306 128×64', ssd1327: 'SSD1327 128×128',
                          none: 'keins gefunden', error: 'Fehler' };
  const HOW = { auto: 'automatisch erkannt', config: 'fest in config.py',
                fallback: 'unbekannt — als SSD1306 angenommen' };
  setText('d_display', (DISPLAY_NAMES[d.display] || d.display) +
          (d.display_address != null ? ' · 0x' + d.display_address.toString(16) : '') +
          (d.display_status != null ? ' · Status 0x' + d.display_status.toString(16) : '') +
          (HOW[d.display_how] ? ' · ' + HOW[d.display_how] : (d.display_how ? ' · ' + d.display_how : '')));
  setText('d_loop', d.loop_dt.toFixed(2) + ' s / ' + d.loop_dt_max.toFixed(2) + ' s');
  setText('d_srv', d.srv_errors);
  setText('d_sd_error', d.sd_error_count ? d.sd_error_txt + ' (' + d.sd_error_at + ', ' +
          d.sd_error_count + '×)' : 'keiner');
}

// The logger's clock does not survive a reset — the phone knows the time.
// Send it once per session while the device reports an unset clock.
async function sendPhoneTime() {
  _timeSent = true;
  try {
    await post('set_time', 'epoch=' + Math.floor(Date.now() / 1000));
  } catch (e) {
    _timeSent = false;
  }
}

// ===== CONTROLS =====
$('toggleShelly').addEventListener('click', async () => {
  const btn = $('toggleShelly');
  btn.disabled = true;
  try {
    const r = await post('toggle_shelly');
    if (!r.ok) throw new Error('HTTP ' + r.status);
    // The logger switches within 0.2 s; then fetch the new state
    await sleep(800);
    await updateData();
  } catch (e) {
    alert('Schalten fehlgeschlagen: ' + errorText(e, 'body'));
  } finally {
    btn.disabled = false;
    btn.blur();
  }
});

$('toggleLogging').addEventListener('click', async () => {
  const btn = $('toggleLogging');
  btn.disabled = true;
  try {
    await post('toggle_logging');
    await updateData();
  } catch (e) {
    alert('Umschalten fehlgeschlagen');
  } finally {
    btn.disabled = false;
    btn.blur();
  }
});

$('timeForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const msg = $('timeResponse');
  msg.textContent = 'Übertragung läuft…';
  try {
    const r = await post('set_time', 'dt=' + encodeURIComponent($('dt').value));
    const d = await r.json();
    if (!d.ok) throw new Error('Ungültige Zeitangabe');
    msg.textContent = '✓ Zeit gesetzt: ' + d.time;
    msg.className = 'status-ok';
  } catch (err) {
    msg.textContent = '❌ ' + (err.message || 'Fehler');
    msg.className = 'status-err';
  }
});

$('wifiBtn').addEventListener('click', () => {
  if (/iPhone|iPad|iPod/i.test(navigator.userAgent)) {
    window.location.href = 'shortcuts://run-shortcut?name=ChangeWIFI';
  } else {
    alert('WLAN-Wechsel nur auf iPhone/iPad verfügbar.');
  }
});

// ===== DATA LOG DOWNLOAD =====
const DL_TIMEOUT = 20000;
const DL_RETRIES = 4;
let _dlCtrl = null;

async function loadLogList() {
  const ul = $('logList');
  try {
    const r = await fetchWithTimeout('log_files');
    const files = await r.json();
    ul.textContent = '';
    if (!files.length) {
      ul.innerHTML = '<li>noch keine Daten</li>';
      return;
    }
    files.reverse().forEach(x => {
      const li = document.createElement('li');
      const name = document.createElement('span');
      name.textContent = x.file + ' · ' + formatBytes(x.size);
      const btn = document.createElement('button');
      btn.textContent = 'Laden';
      btn.className = 'small';
      btn.addEventListener('click', () => downloadLog(x.file, x.size));
      li.append(name, btn);
      ul.append(li);
    });
  } catch (e) {
    ul.innerHTML = '<li>Liste nicht abrufbar</li>';
  }
}

async function downloadLog(file, size) {
  if (_dlCtrl) return;
  const progress = $('dlProgress');
  _dlCtrl = new AbortController();
  $('dlAbort').hidden = false;
  stopPolling();   // status.json should not compete with the download
  const parts = [];
  let offset = 0;
  try {
    while (offset < size) {
      progress.textContent = 'Lade ' + formatBytes(offset) + ' / ' + formatBytes(size) +
                             ' (' + Math.round(offset / size * 100) + ' %)';
      let buf = null;
      for (let attempt = 1; attempt <= DL_RETRIES; attempt++) {
        const ctrl = new AbortController();
        const timer = setTimeout(() => ctrl.abort(), DL_TIMEOUT);
        _dlCtrl.signal.addEventListener('abort', () => ctrl.abort(), { once: true });
        try {
          const r = await fetch('log_stream?file=' + encodeURIComponent(file) +
                                '&offset=' + offset + '&end=' + size,
                                { signal: ctrl.signal, cache: 'no-store' });
          if (!r.ok) throw new Error('HTTP ' + r.status);
          buf = await r.arrayBuffer();   // count bytes, not characters
          break;
        } catch (e) {
          if (_dlCtrl.signal.aborted || attempt === DL_RETRIES) throw e;
          progress.textContent = 'Verbindungsfehler — Versuch ' + (attempt + 1) + '/' + DL_RETRIES;
          await sleep(1500 * attempt);
        } finally {
          clearTimeout(timer);
        }
      }
      if (!buf || !buf.byteLength) break;
      parts.push(buf);
      offset += buf.byteLength;
      await sleep(100);    // give the logger room for its Shelly poll
    }
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob(parts, { type: 'text/csv' }));
    a.download = file;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 10000);
    progress.textContent = 'Fertig — ' + formatBytes(offset);
  } catch (e) {
    progress.textContent = _dlCtrl.signal.aborted ? 'Abgebrochen'
                                                  : 'Fehler: ' + errorText(e, 'body');
  } finally {
    _dlCtrl = null;
    $('dlAbort').hidden = true;
    startPolling();
  }
}

$('dlAbort').addEventListener('click', () => { if (_dlCtrl) _dlCtrl.abort(); });

// ===== DIAGNOSTICS =====
document.querySelectorAll('[data-log]').forEach(btn =>
  btn.addEventListener('click', async () => {
    const url = btn.dataset.log;
    const isHealth = url.startsWith('/health');
    const pre = $(isHealth ? 'pre_health_log' : 'pre_error_log');
    pre.hidden = false;
    pre.textContent = 'lade…';
    try {
      const r = await fetchWithTimeout(url.slice(1), {}, 20000);
      const lines = (await r.text()).trimEnd().split('\n');
      // Newest first, at most 60 lines — the full file stays on the card
      const header = isHealth ? [lines.shift()] : [];
      pre.textContent = header.concat(lines.slice(-60).reverse()).join('\n');
    } catch (e) {
      pre.textContent = 'Fehler: ' + errorText(e, 'body');
    }
  }));

document.querySelectorAll('[data-clear]').forEach(btn =>
  btn.addEventListener('click', async () => {
    if (!confirm('Wirklich leeren?')) return;
    await post(btn.dataset.clear.slice(1));
    document.querySelectorAll('pre[id^="pre_"]').forEach(p => { p.hidden = true; });
  }));

$('connClear').addEventListener('click', () => {
  try { localStorage.removeItem(CONN_KEY); } catch (e) {}
  showConnection();
});

$('remountSd').addEventListener('click', async () => {
  try {
    const d = await (await post('remount_sd')).json();
    alert(d.ok ? 'SD-Karte eingebunden' : 'SD-Karte nicht lesbar');
  } catch (e) { alert('Keine Verbindung'); }
  updateData();
});

$('displayTest').addEventListener('click', async () => {
  try {
    const d = await (await post('display_test')).json();
    alert(d.ok ? 'Das Display zeigt jetzt 8 Sekunden ein Testbild.'
               : 'Kein Display erkannt.');
  } catch (e) { alert('Keine Verbindung'); }
});

$('resetCrashes').addEventListener('click', async () => {
  await post('reset_crashes');
  updateData();
});

// ===== START =====
window.addEventListener('load', () => {
  startPolling();
  loadLogList();
  showConnection();
});
window.addEventListener('online', pollNow);

if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('service-worker.js')
    .catch(err => console.log('SW error:', err));
}
