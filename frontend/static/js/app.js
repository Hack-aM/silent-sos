/**
 * app.js — Silent SOS Dashboard JavaScript
 * ==========================================
 * This file handles ALL dashboard interactivity:
 *
 *  1. Session verification on page load
 *  2. Loading user data, stats, contacts, alerts
 *  3. SOS trigger flow (GPS → API → audio recording → AI analysis)
 *  4. Emergency contact CRUD (add, delete)
 *  5. Logout
 *
 * ARCHITECTURE: Each feature is in its own clearly named function.
 * This keeps the code readable and easy to extend.
 *
 * FRONTEND ↔ BACKEND COMMUNICATION:
 *   All API calls use the Fetch API with credentials: 'include'
 *   so the Flask session cookie is automatically sent.
 */

'use strict';

// ─────────────────────────────────────────────────────────
// GLOBAL STATE
// Tracks active alert and audio recorder across functions
// ─────────────────────────────────────────────────────────
let currentAlertId   = null;  // ID of the active SOS alert
let mediaRecorder    = null;  // MediaRecorder instance for audio
let audioChunks      = [];    // Collected audio data blobs
let isSOSActive      = false; // Prevents double-trigger

// ─────────────────────────────────────────────────────────
// PAGE INIT — Run when DOM is ready
// ─────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  await verifySession();       // 1. Check login
  await loadDashboard();       // 2. Load all data
  await loadEvidenceVault();   // 3. Populate evidence vault
  initShakeDetection();        // 4. Enable shake-to-SOS
});


// ─────────────────────────────────────────────────────────
// 1. SESSION VERIFICATION
// Every page load checks if user is authenticated.
// If not, redirect to login immediately.
// ─────────────────────────────────────────────────────────
async function verifySession() {
  try {
    const res  = await fetch('/api/me', { credentials: 'include' });
    if (!res.ok) {
      // Session expired or not logged in → send to login page
      window.location.href = '/login';
      return;
    }
    const data = await res.json();
    const user = data.user;

    // Populate header with user info
    document.getElementById('userName').textContent  = user.full_name;
    document.getElementById('welcomeName').textContent = user.full_name.split(' ')[0];

    // Set avatar to first letter of name
    document.getElementById('userAvatar').textContent =
      user.full_name.charAt(0).toUpperCase();

  } catch (err) {
    console.error('[AUTH] Session check failed:', err);
    window.location.href = '/login';
  }
}


// ─────────────────────────────────────────────────────────
// 2. LOAD DASHBOARD DATA
// Fetches dashboard summary, contacts, and alert history.
// ─────────────────────────────────────────────────────────
async function loadDashboard() {
  await Promise.all([
    loadStats(),
    loadContacts(),
    loadAlerts(),
    initMap()         // Load Leaflet map with past alert pins
  ]);
}

async function loadStats() {
  try {
    const res  = await fetch('/api/dashboard', { credentials: 'include' });
    const data = await res.json();

    if (res.ok) {
      document.getElementById('statTotal').textContent    = data.stats.total_alerts;
      document.getElementById('statHighRisk').textContent = data.stats.high_risk_events;
      const score = data.stats.latest_ai_score;
      const scoreEl = document.getElementById('statAIScore');
      if (scoreEl) scoreEl.textContent = score !== undefined ? score : '—';
    }
  } catch (err) {
    console.error('[STATS] Failed to load stats:', err);
  }
}


// ─────────────────────────────────────────────────────────
// 3. EMERGENCY CONTACTS — Load, Add, Delete
// ─────────────────────────────────────────────────────────
async function loadContacts() {
  try {
    const res  = await fetch('/api/contacts', { credentials: 'include' });
    const data = await res.json();

    if (res.ok) {
      document.getElementById('statContacts').textContent = data.total;
      renderContacts(data.contacts);
    }
  } catch (err) {
    console.error('[CONTACTS] Failed to load contacts:', err);
  }
}

function renderContacts(contacts) {
  const list = document.getElementById('contactList');

  if (!contacts || contacts.length === 0) {
    list.innerHTML = '<div class="empty-state">No contacts added yet.<br/>Add trusted people above.</div>';
    return;
  }

  list.innerHTML = contacts.map(c => `
    <div class="contact-item" id="contact-${c.id}">
      <div class="contact-info">
        <span class="contact-name">${escapeHtml(c.contact_name)}</span>
        <span class="contact-meta">📞 ${escapeHtml(c.contact_phone)}</span>
      </div>
      <div style="display:flex; gap: 8px; align-items:center;">
        <span class="relation-badge">${escapeHtml(c.relation || 'Contact')}</span>
        <button class="btn btn-ghost" style="padding:0.3rem 0.6rem; font-size:0.75rem;"
          onclick="editContact(${c.id}, '${escapeHtml(c.contact_name)}', '${escapeHtml(c.contact_phone)}', '${escapeHtml(c.relation || '')}')">✎</button>
        <button class="btn btn-danger-outline" onclick="deleteContact(${c.id})">✕</button>
      </div>
    </div>
  `).join('');
}

function toggleContactForm() {
  const wrapper = document.getElementById('contactFormWrapper');
  wrapper.style.display = wrapper.style.display === 'none' ? 'block' : 'none';
  if (wrapper.style.display === 'block') {
    document.getElementById('cName').focus();
  }
}

async function addContact() {
  const contact_name  = document.getElementById('cName').value.trim();
  const contact_phone = document.getElementById('cPhone').value.trim();
  const relation      = document.getElementById('cRelation').value.trim();

  if (!contact_name || !contact_phone) {
    alert('Contact name and phone number are required.');
    return;
  }

  try {
    const res = await fetch('/api/contacts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ contact_name, contact_phone, relation })
    });

    const data = await res.json();

    if (res.ok) {
      // Clear form inputs
      document.getElementById('cName').value    = '';
      document.getElementById('cPhone').value   = '';
      document.getElementById('cRelation').value = '';
      toggleContactForm();
      await loadContacts();  // Refresh contact list
    } else {
      alert(data.error || 'Failed to add contact.');
    }
  } catch (err) {
    alert('Network error. Please try again.');
  }
}

async function deleteContact(contactId) {
  if (!confirm('Remove this emergency contact?')) return;

  try {
    const res = await fetch(`/api/contacts/${contactId}`, {
      method: 'DELETE',
      credentials: 'include'
    });

    if (res.ok) {
      await loadContacts();  // Refresh list
    } else {
      const data = await res.json();
      alert(data.error || 'Failed to delete contact.');
    }
  } catch (err) {
    alert('Network error. Please try again.');
  }
}

/**
 * Edit an existing contact — prompts user then calls PUT endpoint.
 */
async function editContact(contactId, currentName, currentPhone, currentRelation) {
  const name  = prompt('Contact Name:', currentName);
  if (name === null) return;  // cancelled
  const phone = prompt('Phone Number:', currentPhone);
  if (phone === null) return;
  const relation = prompt('Relation:', currentRelation);
  if (relation === null) return;

  if (!name.trim() || !phone.trim()) {
    showToast('⚠️ Name and phone are required.');
    return;
  }

  try {
    const res = await fetch(`/api/contacts/${contactId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({
        contact_name: name.trim(),
        contact_phone: phone.trim(),
        relation: relation ? relation.trim() : ''
      })
    });

    if (res.ok) {
      showToast('✅ Contact updated.');
      await loadContacts();
    } else {
      const data = await res.json();
      showToast(`⚠️ ${data.error || 'Failed to update contact.'}`);
    }
  } catch (err) {
    showToast('⚠️ Network error. Try again.');
  }
}


// ─────────────────────────────────────────────────────────
// 4. ALERT HISTORY — Load and Render
// ─────────────────────────────────────────────────────────
async function loadAlerts() {
  try {
    const res  = await fetch('/api/alerts', { credentials: 'include' });
    const data = await res.json();

    if (res.ok) renderAlerts(data.alerts);

  } catch (err) {
    console.error('[ALERTS] Failed to load alert history:', err);
  }
}

function renderAlerts(alerts) {
  const container = document.getElementById('alertHistory');

  if (!alerts || alerts.length === 0) {
    container.innerHTML = '<div class="empty-state">No alerts triggered yet.<br/>Stay safe!</div>';
    return;
  }

  container.innerHTML = alerts.map(a => {
    const level = a.risk_level || 'UNKNOWN';
    const date  = new Date(a.created_at).toLocaleString('en-IN', {
      dateStyle: 'medium', timeStyle: 'short'
    });
    const coords = (a.latitude && a.longitude)
      ? `📍 ${a.latitude.toFixed(4)}, ${a.longitude.toFixed(4)}`
      : '📍 Location unavailable';

    return `
      <div class="alert-item risk-${level}">
        <div class="alert-dot"></div>
        <div class="alert-details">
          <div style="display:flex; gap:8px; align-items:center; margin-bottom:4px;">
            <span class="alert-risk risk-chip-${level}">${level}</span>
            <span style="font-weight:600; font-size:0.85rem;">Score: ${a.danger_score ?? 0}</span>
          </div>
          <div class="alert-time">${date}</div>
          <div class="alert-time" style="margin-top:2px;">${coords}</div>
          ${a.detected_keywords
            ? `<div class="alert-time" style="color:var(--clr-sos); margin-top:2px;">
                 Keywords: ${escapeHtml(a.detected_keywords)}
               </div>`
            : ''}
        </div>
      </div>
    `;
  }).join('');
}


// ─────────────────────────────────────────────────────────
// 5. SOS TRIGGER FLOW
// This is the core emergency feature.
// Steps: GPS → API → Audio Recording → Upload → AI Analysis
// ─────────────────────────────────────────────────────────
async function triggerSOS() {
  // Prevent accidental double-trigger
  if (isSOSActive) return;
  isSOSActive = true;

  const sosBtn = document.getElementById('sosBtn');
  const sosStatus = document.getElementById('sosStatus');

  // Activate visual state
  sosBtn.classList.add('active');
  sosStatus.classList.add('visible');
  activateStep('step1');

  // STEP 1: Get GPS location
  let latitude  = null;
  let longitude = null;

  try {
    const position = await getGPSLocation();
    latitude  = position.coords.latitude;
    longitude = position.coords.longitude;
    console.log(`[GPS] Location: ${latitude}, ${longitude}`);
  } catch (err) {
    console.warn('[GPS] Location unavailable:', err.message);
    // Continue without GPS — safety is more important than location
  }

  completeStep('step1');
  activateStep('step2');

  // STEP 2: Send SOS alert to backend
  try {
    const res = await fetch('/api/send-sos', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ latitude, longitude })
    });

    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.error || 'SOS API failed');
    }

    currentAlertId = data.alert_id;
    console.log(`[SOS] Alert created: #${currentAlertId}`);

  } catch (err) {
    console.error('[SOS] Failed to send alert:', err);
    resetSOSState();
    alert('Failed to send SOS alert. Please call emergency services directly!');
    return;
  }

  completeStep('step2');
  activateStep('step3');

  // STEP 3: Start audio recording (30 seconds)
  try {
    await startAudioRecording(30000);  // Record for 30 seconds
  } catch (err) {
    console.warn('[AUDIO] Recording failed:', err.message);
    // Audio is optional — proceed to final step
    completeStep('step3');
    completeStep('step4');
    completeStep('step5');
    showEmergencyActivated(null);
    return;
  }
}

/**
 * Get the device's GPS coordinates.
 * Returns a Promise that resolves with the GeolocationPosition.
 * Rejects if the user denies permission or GPS times out.
 */
function getGPSLocation() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error('Geolocation not supported'));
      return;
    }

    navigator.geolocation.getCurrentPosition(resolve, reject, {
      enableHighAccuracy: true,
      timeout: 8000,
      maximumAge: 0
    });
  });
}

/**
 * Start recording audio from the microphone.
 * Records for `durationMs` milliseconds, then uploads the file.
 *
 * HOW MediaRecorder WORKS:
 *  1. Request microphone permission via getUserMedia()
 *  2. Create a MediaRecorder on the audio stream
 *  3. Collect data chunks as they arrive
 *  4. On stop, combine chunks into a Blob and upload
 */
async function startAudioRecording(durationMs) {
  // Request microphone permission from the browser
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

  audioChunks = [];  // Clear any previous data

  // Create recorder — prefer webm/opus for broad browser support
  const options = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
    ? { mimeType: 'audio/webm;codecs=opus' }
    : {};

  mediaRecorder = new MediaRecorder(stream, options);

  // Collect audio data as it becomes available
  mediaRecorder.ondataavailable = (event) => {
    if (event.data && event.data.size > 0) {
      audioChunks.push(event.data);
    }
  };

  // FIX: Handle recording errors gracefully (mic disconnected, permission revoked, etc.)
  mediaRecorder.onerror = (event) => {
    console.error('[AUDIO] MediaRecorder error:', event.error);
    stream.getTracks().forEach(track => track.stop());  // Release mic
    completeStep('step3');
    completeStep('step4');
    completeStep('step5');
    showEmergencyActivated(null);
  };

  // When recording stops, upload the file
  mediaRecorder.onstop = async () => {
    // Stop all microphone tracks (release the mic)
    stream.getTracks().forEach(track => track.stop());

    completeStep('step3');
    activateStep('step4');

    // Combine chunks into a single audio blob
    const audioBlob = new Blob(audioChunks, { type: mediaRecorder.mimeType || 'audio/webm' });

    // FIX: Validate blob is not empty before uploading
    if (audioBlob.size === 0) {
      console.warn('[AUDIO] Empty recording — skipping upload');
      completeStep('step4');
      completeStep('step5');
      showEmergencyActivated(null);
      return;
    }

    const ext = (mediaRecorder.mimeType || 'audio/webm').includes('mp4') ? 'mp4' : 'webm';
    await uploadAudioAndAnalyze(audioBlob, ext);
  };

  // Start recording
  mediaRecorder.start(1000);  // Collect data every 1 second
  console.log('[AUDIO] Recording started');

  // Stop recording after the specified duration
  setTimeout(() => {
    if (mediaRecorder && mediaRecorder.state === 'recording') {
      mediaRecorder.stop();
    }
  }, durationMs);
}

/**
 * Upload the recorded audio blob to the backend,
 * then display the AI danger analysis result.
 */
async function uploadAudioAndAnalyze(audioBlob, ext) {
  const formData = new FormData();
  formData.append('file', audioBlob, `recording.${ext}`);
  formData.append('alert_id', currentAlertId);

  try {
    const res  = await fetch('/api/upload-audio', {
      method: 'POST',
      credentials: 'include',
      body: formData  // No Content-Type header — browser sets it with boundary
    });

    const data = await res.json();

    completeStep('step4');
    completeStep('step5');

    if (res.ok && data.analysis) {
      showEmergencyActivated(data.analysis);
    } else {
      showEmergencyActivated(null);
    }

    // Refresh alert history and evidence vault to show the new entry
    await loadAlerts();
    await loadStats();
    await loadEvidenceVault();

  } catch (err) {
    console.error('[UPLOAD] Audio upload failed:', err);
    completeStep('step4');
    completeStep('step5');
    showEmergencyActivated(null);
  }
}

/**
 * Display the final AI analysis result card on the dashboard.
 */
function showEmergencyActivated(analysis) {
  const subtitle = document.getElementById('sosSubtitle');
  subtitle.textContent = '🔴 Emergency alert is ACTIVE';
  subtitle.style.color = 'var(--clr-sos)';

  if (analysis) {
    const card     = document.getElementById('aiResultCard');
    const bar      = document.getElementById('scoreBarFill');
    const scoreEl  = document.getElementById('scoreValue');
    const chip     = document.getElementById('riskChip');
    const words    = document.getElementById('detectedWords');
    const score    = analysis.danger_score || 0;
    const level    = analysis.risk_level || 'UNKNOWN';

    card.style.display = 'block';

    // Animate the score bar
    setTimeout(() => { bar.style.width = `${score}%`; }, 100);
    scoreEl.textContent = score;

    chip.textContent  = level;
    chip.className    = `alert-risk risk-chip-${level}`;

    words.textContent = analysis.detected_words?.length
      ? `Keywords: ${analysis.detected_words.join(', ')}`
      : 'No specific keywords detected';
  }

  isSOSActive = false;  // Allow re-trigger if needed
}


// ─────────────────────────────────────────────────────────
// STEP ANIMATION HELPERS
// ─────────────────────────────────────────────────────────
function activateStep(stepId) {
  const el = document.getElementById(stepId);
  if (el) {
    el.classList.remove('done');
    el.classList.add('active');
  }
}

function completeStep(stepId) {
  const el = document.getElementById(stepId);
  if (el) {
    el.classList.remove('active');
    el.classList.add('done');
  }
}

function resetSOSState() {
  isSOSActive = false;
  const sosBtn = document.getElementById('sosBtn');
  sosBtn.classList.remove('active');
}


// ─────────────────────────────────────────────────────────
// 6. LOGOUT
// ─────────────────────────────────────────────────────────
async function logout() {
  try {
    await fetch('/api/logout', {
      method: 'POST',
      credentials: 'include'
    });
  } catch (_) { /* ignore errors — always redirect */ }

  window.location.href = '/login';
}


// ─────────────────────────────────────────────────────────
// SECURITY UTILITY: Escape HTML to prevent XSS
// ─────────────────────────────────────────────────────────
function escapeHtml(text) {
  if (typeof text !== 'string') return '';
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}


// ─────────────────────────────────────────────────────────
// 7. LEAFLET.JS ALERT MAP
// Shows color-coded map pins for every past SOS location.
//
// HOW LEAFLET WORKS:
//  1. L.map('elementId') creates a map inside a div
//  2. L.tileLayer() loads map tiles (OpenStreetMap — free)
//  3. L.circleMarker() places a colored dot at each GPS point
//  4. .bindPopup() shows details when the dot is clicked
// ─────────────────────────────────────────────────────────
let leafletMap = null;  // Store map instance globally so we can refresh it

async function initMap() {
  // Safety: Leaflet must be loaded before this runs
  if (typeof L === 'undefined') {
    console.warn('[MAP] Leaflet.js not loaded');
    return;
  }

  try {
    const res  = await fetch('/api/alerts/map', { credentials: 'include' });
    const data = await res.json();
    const points = data.points || [];

    const mapEl  = document.getElementById('alertMap');
    const emptyMsg = document.getElementById('mapEmptyMsg');

    if (!mapEl) return;

    // Initialize Leaflet map centered on India by default
    // (will re-center if we have real GPS points)
    if (!leafletMap) {
      leafletMap = L.map('alertMap', { zoomControl: true }).setView([20.5937, 78.9629], 5);

      // OpenStreetMap tile layer — completely free, no API key
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        maxZoom: 18
      }).addTo(leafletMap);
    }

    if (points.length === 0) {
      emptyMsg.style.display = 'block';
      return;
    }

    emptyMsg.style.display = 'none';

    // Color map: risk level → circle color
    const riskColors = {
      CRITICAL: '#ff2d55',
      HIGH:     '#ff2d55',
      MEDIUM:   '#ff9f0a',
      LOW:      '#30d158',
      NONE:     '#30d158',
      UNKNOWN:  '#8e8e9a'
    };

    const bounds = [];

    points.forEach(point => {
      const color  = riskColors[point.risk_level] || '#8e8e9a';
      const date   = new Date(point.created_at).toLocaleString('en-IN', {
        dateStyle: 'medium', timeStyle: 'short'
      });

      // Draw a colored circle at the GPS location
      const marker = L.circleMarker([point.lat, point.lng], {
        radius:      10,
        fillColor:   color,
        color:       '#fff',
        weight:      2,
        opacity:     0.9,
        fillOpacity: 0.85
      }).addTo(leafletMap);

      // Popup shows alert details when pin is clicked
      marker.bindPopup(`
        <div style="font-family: sans-serif; font-size: 13px; min-width: 160px;">
          <strong style="color:${color};">⚠ ${point.risk_level}</strong><br/>
          <span>Score: ${point.danger_score}/100</span><br/>
          <span style="color:#666;">${date}</span><br/>
          <a href="https://maps.google.com/?q=${point.lat},${point.lng}"
             target="_blank" style="color:#0a84ff;">Open in Google Maps ↗</a>
        </div>
      `);

      bounds.push([point.lat, point.lng]);
    });

    // Auto-fit the map to show all alert pins
    if (bounds.length > 0) {
      leafletMap.fitBounds(bounds, { padding: [40, 40], maxZoom: 14 });
    }

    console.log(`[MAP] Rendered ${points.length} alert pin(s)`);

  } catch (err) {
    console.error('[MAP] Failed to load map data:', err);
  }
}


// ─────────────────────────────────────────────────────────
// 8. SHAKE DETECTION — Triple Shake triggers SOS silently
// ─────────────────────────────────────────────────────────
let shakeCount = 0;
let shakeLastTime = 0;
let shakeLast = { x: 0, y: 0, z: 0 };
let shakeResetTimer = null;  // FIX: Track the reset timeout to avoid accumulation

function initShakeDetection() {
  if (!window.DeviceMotionEvent) return;

  if (typeof DeviceMotionEvent.requestPermission === 'function') {
    // iOS 13+ requires explicit permission
    document.addEventListener('click', async () => {
      try { await DeviceMotionEvent.requestPermission(); } catch (_) {}
    }, { once: true });
  }

  window.addEventListener('devicemotion', (e) => {
    const acc = e.accelerationIncludingGravity;
    if (!acc) return;
    const now = Date.now();
    if (now - shakeLastTime < 100) return;

    const dx = Math.abs(acc.x - shakeLast.x);
    const dy = Math.abs(acc.y - shakeLast.y);
    const dz = Math.abs(acc.z - shakeLast.z);

    if (dx + dy + dz > 25) {
      shakeCount++;
      console.log(`[SHAKE] Count: ${shakeCount}`);
      if (shakeCount >= 3) {
        shakeCount = 0;
        console.log('[SHAKE] Triple shake — triggering SOS');
        triggerSOS();
      }
      shakeLastTime = now;
    }
    shakeLast = { x: acc.x, y: acc.y, z: acc.z };

    // FIX: Clear previous timer before setting new one (prevents timer stacking)
    if (shakeResetTimer) clearTimeout(shakeResetTimer);
    shakeResetTimer = setTimeout(() => { shakeCount = 0; }, 2000);
  });
}


// ─────────────────────────────────────────────────────────
// 9. CALCULATOR STEALTH MODE
// ─────────────────────────────────────────────────────────
const SECRET_PIN = '1234='; // Change this to your secret PIN
let calcBuffer = '';
let calcExpression = '';

function enableCalculatorMode() {
  document.getElementById('calculatorOverlay').style.display = 'flex';
  calcBuffer = '';
  calcExpression = '';
  updateCalcDisplay();
}

function calcInput(key) {
  if (key === 'C') {
    calcBuffer = '';
    calcExpression = '';
    updateCalcDisplay();
    return;
  }

  calcBuffer += key;

  if (key === '=') {
    // Check secret PIN before evaluating
    if (calcBuffer === SECRET_PIN) {
      document.getElementById('calculatorOverlay').style.display = 'none';
      calcBuffer = '';
      return;
    }
    try {
      let expr = calcExpression
        .replace(/÷/g, '/')
        .replace(/×/g, '*')
        .replace(/−/g, '-');
      let result = Function('"use strict"; return (' + expr + ')')();
      document.getElementById('calcResult').textContent =
        isFinite(result) ? parseFloat(result.toFixed(8)) : 'Error';
      calcExpression = '';
    } catch (_) {
      document.getElementById('calcResult').textContent = 'Error';
      calcExpression = '';
    }
    calcBuffer = '';
    updateCalcDisplay();
    return;
  }

  if (['+', '-', '×', '÷'].includes(key)) {
    calcExpression += document.getElementById('calcResult').textContent + key;
    document.getElementById('calcExpr').textContent = calcExpression;
    document.getElementById('calcResult').textContent = '0';
    calcBuffer = '';
    return;
  }

  if (key === '+/-') {
    let v = parseFloat(document.getElementById('calcResult').textContent) * -1;
    document.getElementById('calcResult').textContent = v;
    return;
  }
  if (key === '%') {
    let v = parseFloat(document.getElementById('calcResult').textContent) / 100;
    document.getElementById('calcResult').textContent = v;
    return;
  }

  // Normal digit / decimal
  let current = document.getElementById('calcResult').textContent;
  if (current === '0' && key !== '.') {
    document.getElementById('calcResult').textContent = key;
  } else {
    document.getElementById('calcResult').textContent = current + key;
  }
}

function updateCalcDisplay() {
  document.getElementById('calcResult').textContent = '0';
  document.getElementById('calcExpr').textContent = '';
}


// ─────────────────────────────────────────────────────────
// 10. FAKE CALL FEATURE
// ─────────────────────────────────────────────────────────
let fakeCallTimer = null;
let fakeCallOngoingTimer = null;  // FIX: Track the on-call interval to prevent leaks

function startFakeCall() {
  const panel = document.getElementById('fakeCallSetup');
  panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
}

function scheduleFakeCall() {
  const name  = document.getElementById('fakeCallerInput').value.trim() || 'Mom';
  const delay = parseInt(document.getElementById('fakeCallDelay').value) || 5;

  document.getElementById('fakeCallSetup').style.display = 'none';
  showToast(`📞 Fake call from "${name}" in ${delay}s…`);

  // FIX: Clear any previous pending fake call before scheduling new one
  if (fakeCallTimer) clearTimeout(fakeCallTimer);
  fakeCallTimer = setTimeout(() => showFakeCallOverlay(name), delay * 1000);
}

function showFakeCallOverlay(name) {
  document.getElementById('fakeCallerName').textContent = name + ' Calling…';
  document.getElementById('fakeCallStatus').textContent = 'incoming call';
  document.getElementById('fakeCallOverlay').style.display = 'flex';
}

function acceptFakeCall() {
  document.getElementById('fakeCallStatus').textContent = '00:00 · on call…';
  let secs = 0;
  // FIX: Store the interval so it can be cleared on end
  fakeCallOngoingTimer = setInterval(() => {
    secs++;
    const m = String(Math.floor(secs / 60)).padStart(2, '0');
    const s = String(secs % 60).padStart(2, '0');
    document.getElementById('fakeCallStatus').textContent = `${m}:${s} · on call…`;
  }, 1000);
  setTimeout(() => { endFakeCall(); }, 30000);
}

function endFakeCall() {
  document.getElementById('fakeCallOverlay').style.display = 'none';
  if (fakeCallTimer) { clearTimeout(fakeCallTimer); fakeCallTimer = null; }
  // FIX: Clear the on-call timer to prevent memory leak
  if (fakeCallOngoingTimer) { clearInterval(fakeCallOngoingTimer); fakeCallOngoingTimer = null; }
}


// ─────────────────────────────────────────────────────────
// 11. SAFE JOURNEY MODE
// ─────────────────────────────────────────────────────────
let journeyTimer = null;
let journeyActive = false;
let journeySecondsLeft = 0;

function toggleSafeJourney() {
  const panel = document.getElementById('safeJourneyPanel');
  panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
}

function startSafeJourney() {
  // FIX: Prevent double-start — cancel existing journey first
  if (journeyActive) {
    cancelSafeJourney();
    return;
  }

  const dest    = document.getElementById('journeyDest').value.trim() || 'destination';
  const minutes = parseInt(document.getElementById('journeyTime').value) || 30;

  if (minutes < 1 || minutes > 480) {
    showToast('⚠️ Please set a journey time between 1 and 480 minutes.');
    return;
  }

  journeySecondsLeft = minutes * 60;
  journeyActive = true;

  document.getElementById('safeJourneyBadge').style.display = 'flex';
  document.getElementById('journeyStartBtn').textContent = '⏹ Cancel Journey';
  document.getElementById('journeyStartBtn').onclick = cancelSafeJourney;

  const status = document.getElementById('journeyStatus');
  status.classList.add('visible');

  journeyTimer = setInterval(() => {
    journeySecondsLeft--;
    const m = Math.floor(journeySecondsLeft / 60);
    const s = journeySecondsLeft % 60;
    status.innerHTML = `
      🛤️ Safe Journey to <strong>${escapeHtml(dest)}</strong><br>
      <div class="journey-timer">${m}:${String(s).padStart(2,'0')}</div>
      <small>remaining — if this reaches 0 with no check-in, SOS activates</small>
    `;

    if (journeySecondsLeft <= 0) {
      clearInterval(journeyTimer);
      journeyTimer = null;
      status.innerHTML = '🚨 Journey time expired! Auto-triggering SOS…';
      triggerSOS();
      journeyActive = false;
      document.getElementById('safeJourneyBadge').style.display = 'none';
    }
  }, 1000);
}

function cancelSafeJourney() {
  clearInterval(journeyTimer);
  journeyActive = false;
  document.getElementById('safeJourneyBadge').style.display = 'none';
  document.getElementById('journeyStatus').classList.remove('visible');
  document.getElementById('journeyStartBtn').textContent = '🚀 Start Safe Journey';
  document.getElementById('journeyStartBtn').onclick = startSafeJourney;
  document.getElementById('safeJourneyPanel').style.display = 'none';
  showToast('✅ Safe Journey cancelled. Stay safe!');
}


// ─────────────────────────────────────────────────────────
// 12. "I'M SAFE" CHECK-IN
// ─────────────────────────────────────────────────────────
async function doSafeCheckIn() {
  if (journeyActive) {
    cancelSafeJourney();
    showToast('✅ Safe check-in confirmed! Journey ended safely.');
  }
  try {
    await fetch('/api/safe-checkin', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ timestamp: new Date().toISOString() })
    });
  } catch (_) {}
  showToast('✅ Safe check-in recorded!');
}


// ─────────────────────────────────────────────────────────
// 13. REPORT UNSAFE AREA
// ─────────────────────────────────────────────────────────
async function reportUnsafeArea() {
  let lat = null, lng = null;
  try {
    const pos = await getGPSLocation();
    lat = pos.coords.latitude;
    lng = pos.coords.longitude;
  } catch (_) {}

  const description = prompt('Describe the unsafe situation briefly (optional):') || '';

  try {
    const res = await fetch('/api/report-unsafe', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ latitude: lat, longitude: lng, description })
    });
    if (res.ok) {
      showToast('⚠️ Unsafe area reported. Thank you for keeping others safe!');
    }
  } catch (_) {
    showToast('⚠️ Area report saved locally.');
  }
}


// ─────────────────────────────────────────────────────────
// 14. NIGHT SAFETY MODE
// ─────────────────────────────────────────────────────────
let nightModeActive = false;

function toggleNightMode() {
  nightModeActive = !nightModeActive;
  document.body.classList.toggle('night-mode', nightModeActive);
  const bar = document.getElementById('nightModeBar');
  bar.style.display = nightModeActive ? 'block' : 'none';
  const btn = document.getElementById('nightModeBtn');
  btn.style.background = nightModeActive ? 'rgba(255,159,10,0.2)' : '';
  showToast(nightModeActive ? '🌙 Night Safety Mode activated' : '☀️ Night Mode disabled');
}


// ─────────────────────────────────────────────────────────
// 15. EVIDENCE VAULT — Load audio recordings from alerts
// ─────────────────────────────────────────────────────────
async function loadEvidenceVault() {
  try {
    const res  = await fetch('/api/alerts', { credentials: 'include' });
    const data = await res.json();
    const vault = document.getElementById('evidenceVault');

    const withAudio = (data.alerts || []).filter(a => a.audio_filename);
    if (withAudio.length === 0) return;

    // FIX: Added <audio> player for each evidence file so recordings can be reviewed
    vault.innerHTML = withAudio.map(a => {
      const date = new Date(a.created_at).toLocaleString('en-IN', {
        dateStyle: 'medium', timeStyle: 'short'
      });
      return `
        <div class="evidence-item" style="flex-wrap:wrap;">
          <div class="evidence-icon">🎙️</div>
          <div class="evidence-info">
            <div class="evidence-name">${escapeHtml(a.audio_filename)}</div>
            <div class="evidence-meta">${date} · Score: ${a.danger_score}/100 · ${a.risk_level}</div>
          </div>
          <span class="alert-risk risk-chip-${a.risk_level}">${a.risk_level}</span>
          <audio controls preload="none" style="width:100%; margin-top:8px; border-radius:8px; height:36px;">
            <source src="/api/audio/${encodeURIComponent(a.audio_filename)}" type="audio/webm">
            <source src="/api/audio/${encodeURIComponent(a.audio_filename)}" type="audio/mpeg">
            Your browser does not support audio playback.
          </audio>
        </div>
      `;
    }).join('');
  } catch (err) {
    console.error('[VAULT] Failed to load evidence:', err);
  }
}


// ─────────────────────────────────────────────────────────
// 16. TOAST NOTIFICATION HELPER
// ─────────────────────────────────────────────────────────
function showToast(message, duration = 3500) {
  let toast = document.getElementById('soToast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'soToast';
    toast.style.cssText = `
      position:fixed; bottom:24px; left:50%; transform:translateX(-50%);
      background:rgba(26,26,36,0.95); color:#f2f2f7;
      border:1px solid rgba(255,255,255,0.1);
      padding:12px 20px; border-radius:12px;
      font-size:0.88rem; font-weight:600;
      box-shadow:0 8px 32px rgba(0,0,0,0.5);
      z-index:99999; backdrop-filter:blur(12px);
      transition:opacity 0.3s ease;
    `;
    document.body.appendChild(toast);
  }
  toast.textContent = message;
  toast.style.opacity = '1';
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => { toast.style.opacity = '0'; }, duration);
}


// ═════════════════════════════════════════════════════════
// 17. LIVE TRACKING MAP MODULE
// Real-time GPS tracking with Leaflet, animated pulse,
// route polyline, speed/duration stats, and route log.
//
// ARCHITECTURE:
//   Uses dedicated /api/tracking/* endpoints so that GPS
//   updates are stored in tracking_sessions/tracking_points
//   tables — NOT in the alerts table.
// ═════════════════════════════════════════════════════════
let ltMap          = null;   // Leaflet map instance
let ltMarker       = null;   // Current position marker
let ltPolyline     = null;   // Route trail line
let ltWatchId      = null;   // Geolocation watchPosition ID
let ltIsTracking   = false;
let ltUpdateCount  = 0;
let ltStartTime    = null;
let ltDurationTimer = null;
let ltRoutePoints  = [];     // Array of [lat, lng] for polyline
let ltSessionId    = null;   // Backend tracking session ID

/**
 * Initialize the live tracking Leaflet map.
 * Called once on page load — creates map but doesn't start tracking.
 */
function initLiveTrackMap() {
  if (typeof L === 'undefined') return;
  const el = document.getElementById('liveTrackMap');
  if (!el || ltMap) return;

  ltMap = L.map('liveTrackMap', {
    zoomControl: true,
    attributionControl: false
  }).setView([20.5937, 78.9629], 5);

  // Dark-themed tile layer to match the glassmorphism card
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    maxZoom: 19,
    subdomains: 'abcd'
  }).addTo(ltMap);

  // Small attribution text
  L.control.attribution({
    prefix: '<a href="https://carto.com" style="color:#555">CARTO</a> · <a href="https://osm.org" style="color:#555">OSM</a>'
  }).addTo(ltMap);
}

/**
 * Toggle live tracking on/off.
 */
function toggleLiveTracking() {
  if (ltIsTracking) {
    stopLiveTracking();
  } else {
    startLiveTracking();
  }
}

/**
 * Start live GPS tracking — creates a backend tracking session
 * and watches position every ~3-10s via Geolocation API.
 */
async function startLiveTracking() {
  if (!navigator.geolocation) {
    showToast('⚠️ Geolocation is not supported by your browser.');
    return;
  }

  // STEP 1: Create a tracking session on the backend
  try {
    const res = await fetch('/api/tracking/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include'
    });

    const data = await res.json();

    if (!res.ok) {
      showToast('⚠️ Failed to start tracking session.');
      console.error('[TRACK] Start failed:', data.error);
      return;
    }

    ltSessionId = data.session_id;
    console.log(`[TRACK] Session #${ltSessionId} created on backend`);

  } catch (err) {
    showToast('⚠️ Network error. Tracking started locally only.');
    console.error('[TRACK] Start request failed:', err);
    ltSessionId = null;  // Will track locally without backend persistence
  }

  // STEP 2: Initialize local tracking state
  ltIsTracking  = true;
  ltUpdateCount = 0;
  ltStartTime   = Date.now();
  ltRoutePoints = [];

  // STEP 3: Update UI to active state
  const badge  = document.getElementById('ltBadge');
  const btn    = document.getElementById('ltToggleBtn');
  const pulse  = document.getElementById('ltPulseOverlay');
  const info   = document.getElementById('ltInfoBar');
  const log    = document.getElementById('ltRouteLog');

  badge.classList.add('active');
  document.getElementById('ltBadgeText').textContent = 'Tracking Active';
  btn.textContent = '■ Stop Tracking';
  btn.classList.add('tracking');
  pulse.style.display = 'flex';
  info.style.display  = 'grid';
  log.style.display   = 'block';

  // Start duration timer
  ltDurationTimer = setInterval(updateTrackDuration, 1000);

  // STEP 4: Watch position with high accuracy
  ltWatchId = navigator.geolocation.watchPosition(
    (pos) => onTrackingUpdate(pos),
    (err) => {
      console.warn('[TRACK] GPS error:', err.message);
      document.getElementById('ltCoords').textContent = 'GPS unavailable';
    },
    {
      enableHighAccuracy: true,
      timeout: 10000,
      maximumAge: 3000
    }
  );

  // Ensure map is sized correctly
  if (ltMap) setTimeout(() => ltMap.invalidateSize(), 200);

  showToast('📡 Live tracking started');
  console.log('[TRACK] Live tracking activated');
}

/**
 * Handle each GPS position update.
 */
function onTrackingUpdate(position) {
  const lat = position.coords.latitude;
  const lng = position.coords.longitude;
  const spd = position.coords.speed;  // m/s or null

  ltUpdateCount++;
  ltRoutePoints.push([lat, lng]);

  // Update info bar
  document.getElementById('ltCoords').textContent =
    `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
  document.getElementById('ltSpeed').textContent =
    spd !== null ? `${(spd * 3.6).toFixed(1)} km/h` : '—';
  document.getElementById('ltUpdates').textContent = ltUpdateCount;

  // Update map view
  if (ltMap) {
    ltMap.setView([lat, lng], Math.max(ltMap.getZoom(), 15));

    // Move or create marker
    if (ltMarker) {
      ltMarker.setLatLng([lat, lng]);
    } else {
      ltMarker = L.circleMarker([lat, lng], {
        radius: 8,
        fillColor: '#0a84ff',
        color: '#fff',
        weight: 2,
        fillOpacity: 0.9
      }).addTo(ltMap);
    }

    // Update route polyline
    if (ltPolyline) {
      ltPolyline.setLatLngs(ltRoutePoints);
    } else {
      ltPolyline = L.polyline(ltRoutePoints, {
        color: '#0a84ff',
        weight: 3,
        opacity: 0.7,
        dashArray: '8 4'
      }).addTo(ltMap);
    }
  }

  // Add route log entry (keep last 20)
  addRouteLogEntry(lat, lng);

  // Send position to backend tracking endpoint (not /send-sos!)
  sendTrackingUpdate(lat, lng, spd);
}

/**
 * Add a timestamped entry to the route log panel.
 */
function addRouteLogEntry(lat, lng) {
  const entries = document.getElementById('ltRouteEntries');
  const time    = new Date().toLocaleTimeString('en-IN', {
    hour: '2-digit', minute: '2-digit', second: '2-digit'
  });

  const entry = document.createElement('div');
  entry.className = 'lt-route-entry';
  entry.innerHTML = `
    <span class="lt-route-time">${time}</span>
    <span>📍 ${lat.toFixed(4)}, ${lng.toFixed(4)}</span>
  `;

  entries.prepend(entry);

  // Keep only the last 20 entries
  while (entries.children.length > 20) {
    entries.removeChild(entries.lastChild);
  }
}

/**
 * Send tracking coordinate to the dedicated tracking API.
 * Uses /api/tracking/update — NOT /api/send-sos.
 * This stores the GPS point in tracking_points table,
 * keeping the alerts table clean for real emergencies only.
 */
async function sendTrackingUpdate(lat, lng, speed) {
  if (!ltSessionId) return;  // No backend session — skip

  try {
    await fetch('/api/tracking/update', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({
        latitude: lat,
        longitude: lng,
        speed: speed,
        session_id: ltSessionId
      })
    });
  } catch (_) {
    // Silent — tracking updates are best-effort
  }
}

/**
 * Update the duration display.
 */
function updateTrackDuration() {
  if (!ltStartTime) return;
  const elapsed = Math.floor((Date.now() - ltStartTime) / 1000);
  const m = String(Math.floor(elapsed / 60)).padStart(2, '0');
  const s = String(elapsed % 60).padStart(2, '0');
  document.getElementById('ltDuration').textContent = `${m}:${s}`;
}

/**
 * Stop live tracking — notifies backend, clears GPS watch, resets UI.
 */
async function stopLiveTracking() {
  ltIsTracking = false;

  // Stop GPS watch
  if (ltWatchId !== null) {
    navigator.geolocation.clearWatch(ltWatchId);
    ltWatchId = null;
  }

  // Stop duration timer
  if (ltDurationTimer) {
    clearInterval(ltDurationTimer);
    ltDurationTimer = null;
  }

  // Notify backend to close the tracking session
  if (ltSessionId) {
    try {
      await fetch('/api/tracking/stop', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include'
      });
      console.log(`[TRACK] Session #${ltSessionId} closed on backend`);
    } catch (_) {
      // Best-effort — session will auto-close on next start
    }
    ltSessionId = null;
  }

  // Reset UI
  const badge = document.getElementById('ltBadge');
  const btn   = document.getElementById('ltToggleBtn');
  const pulse = document.getElementById('ltPulseOverlay');

  badge.classList.remove('active');
  document.getElementById('ltBadgeText').textContent = 'Standby';
  btn.textContent = 'Start Tracking';
  btn.classList.remove('tracking');
  pulse.style.display = 'none';

  showToast('📡 Live tracking stopped');
  console.log(`[TRACK] Stopped. ${ltUpdateCount} updates recorded.`);
}

/**
 * Auto-start tracking when SOS is triggered.
 * Called from the existing triggerSOS flow.
 */
function autoStartTrackingOnSOS() {
  if (!ltIsTracking) {
    startLiveTracking();
  }
}

// ── Hook into page load to init the map ──────────────────
// Uses a second DOMContentLoaded (additive, doesn't conflict)
document.addEventListener('DOMContentLoaded', () => {
  initLiveTrackMap();
});

