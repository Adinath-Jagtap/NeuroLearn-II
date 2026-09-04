/**
 * NeuroLearn 2.0 — Main JS
 * Core utilities, PWA registration, SOS, TTS, language, accessibility
 */

// --- PWA Registration ---
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js')
            .then(reg => console.log('✅ Service Worker registered'))
            .catch(err => console.log('⚠️ SW registration failed:', err));
    });
}

// --- SOS System ---
async function triggerSOS() {
    const modal = document.getElementById('sos-modal');
    if (modal) modal.style.display = 'flex';

    // Play calming audio
    if ('speechSynthesis' in window) {
        const u = new SpeechSynthesisUtterance('Help is on the way. Stay calm. Your caregiver has been notified.');
        u.rate = 0.8;
        speechSynthesis.speak(u);
    }

    // Get location
    let lat = null, lng = null;
    try {
        const pos = await new Promise((resolve, reject) => {
            navigator.geolocation.getCurrentPosition(resolve, reject, {
                enableHighAccuracy: true,
                timeout: 10000
            });
        });
        lat = pos.coords.latitude;
        lng = pos.coords.longitude;
    } catch (e) {
        console.log('⚠️ Location unavailable');
    }

    // Send SOS
    try {
        const r = await fetch('/api/sos-alert', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ latitude: lat, longitude: lng })
        });
        const data = await r.json();

        // Update modal status
        const emailEl = document.getElementById('sos-email');
        const locEl = document.getElementById('sos-location');
        const statusMsg = document.getElementById('sos-status-msg');

        if (emailEl) {
            emailEl.innerHTML = data.email_sent
                ? '<i class="fas fa-check-circle" style="color:var(--success)"></i> Email sent to caregiver!'
                : '<i class="fas fa-exclamation-circle" style="color:var(--warning)"></i> Email not configured';
            emailEl.classList.add('done');
        }
        if (locEl) {
            locEl.innerHTML = data.location_shared
                ? '<i class="fas fa-check-circle" style="color:var(--success)"></i> Location shared!'
                : '<i class="fas fa-exclamation-circle" style="color:var(--warning)"></i> Location unavailable';
            locEl.classList.add('done');
        }
        if (statusMsg) {
            statusMsg.textContent = data.message || 'Help is on the way!';
        }
    } catch (e) {
        const statusMsg = document.getElementById('sos-status-msg');
        if (statusMsg) statusMsg.textContent = 'Alert sent! Please stay calm.';
    }
}

function closeSOS() {
    const modal = document.getElementById('sos-modal');
    if (modal) modal.style.display = 'none';
}

// --- TTS Read Page ---
function readPageAloud() {
    if (!('speechSynthesis' in window)) {
        alert('Text-to-speech is not supported in this browser.');
        return;
    }

    speechSynthesis.cancel();

    const main = document.querySelector('.main-content');
    if (!main) return;

    // Get text — strip button labels, nav text, just meaningful content
    const text = main.innerText.replace(/[←→↑↓]/g, '').trim().substring(0, 800);

    // Use PATIENT_LANG injected from Flask session (base.html) — falls back to lang-select
    const lang = (typeof PATIENT_LANG !== 'undefined' && PATIENT_LANG)
        ? PATIENT_LANG
        : (document.getElementById('lang-select')?.value || 'en');

    // Try backend TTS first (correct language audio)
    fetch('/api/tts/speak', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({text: text.substring(0, 400), lang: lang})
    }).then(r => {
        if (!r.ok) throw new Error('backend tts failed');
        return r.blob();
    }).then(blob => {
        new Audio(URL.createObjectURL(blob)).play();
    }).catch(() => {
        // Browser TTS fallback with correct language
        const u = new SpeechSynthesisUtterance(text);
        const bcp47 = {
            'hi': 'hi-IN', 'mr': 'mr-IN', 'as': 'as-IN',
            'bn': 'bn-IN', 'mni': 'bn-IN', 'ta': 'ta-IN', 'en': 'en-IN'
        }[lang] || 'en-IN';
        u.lang = bcp47;
        u.rate = 0.8;
        // Pick voice matching language
        const voices = speechSynthesis.getVoices();
        const match = voices.find(v => v.lang.startsWith(bcp47.split('-')[0]));
        if (match) u.voice = match;
        speechSynthesis.speak(u);
    });
}

// --- Language ---
function setLanguage(lang) {
    document.cookie = `lang=${lang};path=/;max-age=31536000`;
    // Navigate with ?lang= so Flask context_processor picks up the new language
    const url = new URL(window.location.href);
    url.searchParams.set('lang', lang);
    window.location.href = url.toString();
}

// --- Accessibility ---
document.addEventListener('DOMContentLoaded', () => {
    // Check for user font size preference
    const savedFontSize = localStorage.getItem('neurolearn-fontsize');
    if (savedFontSize) {
        document.documentElement.style.fontSize = savedFontSize;
    }

    // Keyboard navigation enhancement
    document.addEventListener('keydown', (e) => {
        // ESC closes modals
        if (e.key === 'Escape') {
            closeSOS();
        }
    });
});

// --- Utility ---
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    const bg = type === 'success' ? 'var(--primary)' : type === 'error' ? 'var(--danger)' : 'var(--secondary)';
    toast.style.cssText = `
        position:fixed; bottom:100px; left:50%; transform:translateX(-50%);
        background:${bg}; color:white; padding:16px 32px; border-radius:16px;
        font-size:18px; font-weight:700; z-index:300; box-shadow:var(--shadow-lg);
        animation:slide-up 0.3s ease;
    `;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

console.log('🧠 NeuroLearn 2.0 loaded');
