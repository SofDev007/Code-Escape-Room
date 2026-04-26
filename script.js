// MATRIX RAIN
const canvas = document.getElementById('matrixCanvas');
const ctx = canvas.getContext('2d');

const CHARS = '01010101010101010101010101010101010101010101010101010101010101010101010101010';
let drops = [];
let fontSize = 18;

function resizeCanvas() {
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
  const cols = Math.floor(canvas.width / fontSize);
  drops = Array.from({ length: cols }, () => Math.random() * -100);
}

function drawMatrix() {
  ctx.fillStyle = 'rgba(2, 12, 2, 0.055)';
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  drops.forEach((y, i) => {
    const char = CHARS[Math.floor(Math.random() * CHARS.length)];
    const x = i * fontSize;

    // Head glow — bright
    ctx.fillStyle = '#00ff41';
    ctx.shadowColor = '#00ff41';
    ctx.shadowBlur = 8;
    ctx.font = `${fontSize}px 'Share Tech Mono', monospace`;
    ctx.fillText(char, x, y * fontSize);

    // Trail — dimmer
    ctx.shadowBlur = 0;
    ctx.fillStyle = '#00c832';
    if (y > 1) {
      const trailChar = CHARS[Math.floor(Math.random() * CHARS.length)];
      ctx.fillText(trailChar, x, (y - 1) * fontSize);
    }

    if (y * fontSize > canvas.height && Math.random() > 0.975) {
      drops[i] = 0;
    }
    drops[i] += 0.5;
  });
}

resizeCanvas();
window.addEventListener('resize', resizeCanvas);
setInterval(drawMatrix, 45);


// ── BOOT SEQUENCE ────────────────────────────
const BOOT_DURATION = 6200; // ms

window.addEventListener('DOMContentLoaded', () => {
  setTimeout(() => {
    const boot = document.getElementById('bootScreen');
    boot.classList.add('fade-out');
    setTimeout(() => {
      boot.style.display = 'none';
      document.getElementById('mainScreen').classList.remove('hidden');
      initMain();
    }, 600);
  }, BOOT_DURATION);
});


// ── INIT MAIN ────────────────────────────────
function initMain() {
  typePrompt();
  loadLeaderboard();
  loadStats();

  // Difficulty buttons
  const HINTS = { easy:5, medium:3, hard:1 };
  document.querySelectorAll('.diff-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.diff-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      sessionStorage.setItem('cer_diff', btn.dataset.diff);
      const hintsEl = document.getElementById('hintsDisplay');
      if (hintsEl) hintsEl.textContent = HINTS[btn.dataset.diff] || 3;
    });
  });
}


// ── TYPING PROMPT ANIMATION ──────────────────
const PROMPTS = [
  'AWAITING AGENT IDENTIFICATION...',
  'SYSTEM BREACH IN PROGRESS...',
  'ESCAPE WINDOW: LIMITED...',
  'CRACK THE CODE. SURVIVE.',
];
let promptIdx = 0;
let charIdx = 0;
let typingTimer;

function typePrompt() {
  const el = document.getElementById('typedPrompt');
  const txt = PROMPTS[promptIdx];
  if (charIdx <= txt.length) {
    el.textContent = txt.slice(0, charIdx);
    charIdx++;
    typingTimer = setTimeout(typePrompt, 55);
  } else {
    setTimeout(() => {
      charIdx = 0;
      promptIdx = (promptIdx + 1) % PROMPTS.length;
      typePrompt();
    }, 2200);
  }
}


// ── LEADERBOARD ──────────────────────────────
async function loadLeaderboard() {
  const token = localStorage.getItem('cer_token');
  if (!token) return;

  try {
    const res = await fetch('/api/leaderboard/overall', {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    if (!res.ok) throw new Error('API Error');
    const data = await res.json();
    renderLeaderboard(data.leaderboard || []);
  } catch (err) {
    console.error('Leaderboard error:', err);
    const list = document.getElementById('leaderboardList');
    if (list) list.innerHTML = '<div class="lb-empty">&gt; ERROR SYNCING DATA</div>';
  }
}

function formatTime(seconds) {
  if (!seconds) return '00:00';
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

function saveScore(name, score, timeStr) {
  // Legacy local storage - optionally keep for offline but secondary
  try {
    const lb = JSON.parse(localStorage.getItem('cer_leaderboard') || '[]');
    lb.push({ name: name.toUpperCase(), score, time: timeStr, ts: Date.now() });
    localStorage.setItem('cer_leaderboard', JSON.stringify(lb.slice(0, 10)));
  } catch (e) {}
}

function renderLeaderboard(scores) {
  const list = document.getElementById('leaderboardList');
  if (!list) return;

  if (!scores.length) {
    list.innerHTML = '<div class="lb-empty">&gt; NO ENTRIES YET. BE THE FIRST TO ESCAPE.</div>';
    return;
  }

  const medals = ['🥇', '🥈', '🥉'];
  list.innerHTML = scores.map((s, i) => `
    <div class="lb-entry ${i < 3 ? `rank-${i + 1}` : ''} ${s.is_me ? 'is-me' : ''}">
      <span>${medals[i] || (i + 1)}</span>
      <span class="lb-name">${s.name} ${s.is_me ? '<span class="me-tag">(YOU)</span>' : ''}</span>
      <span class="lb-score">${s.total_score || s.score || 0}</span>
      <span class="lb-time">${s.total_time ? formatTime(s.total_time) : (s.time || '00:00')}</span>
    </div>
  `).join('');
}


// ── STATS ────────────────────────────────────
const STATS_KEY = 'cer_stats';

function loadStats() {
  const s = getStatsData();
  document.getElementById('statAttempts').textContent = s.attempts;
  document.getElementById('statEscapes').textContent = s.escapes;
}

function getStatsData() {
  try {
    return JSON.parse(localStorage.getItem(STATS_KEY)) || { attempts: 0, escapes: 0 };
  } catch {
    return { attempts: 0, escapes: 0 };
  }
}

function updateStats(scores) {
  const s = getStatsData();
  document.getElementById('statAttempts').textContent = s.attempts;
  document.getElementById('statEscapes').textContent = s.escapes;
}

function incrementAttempts() {
  const s = getStatsData();
  s.attempts = (s.attempts || 0) + 1;
  localStorage.setItem(STATS_KEY, JSON.stringify(s));
  document.getElementById('statAttempts').textContent = s.attempts;
}

function incrementEscapes() {
  const s = getStatsData();
  s.escapes = (s.escapes || 0) + 1;
  localStorage.setItem(STATS_KEY, JSON.stringify(s));
  document.getElementById('statEscapes').textContent = s.escapes;
}


// ── START GAME ───────────────────────────────
function startGame() {
  // Validate room selection
  if (typeof selectedRooms === 'undefined' || selectedRooms.size === 0) {
    // Flash the grid
    const grid = document.getElementById('roomSelectGrid');
    if (grid) {
      grid.style.outline = '1px solid var(--red)';
      grid.style.boxShadow = '0 0 14px rgba(255,34,51,0.3)';
      setTimeout(() => { grid.style.outline=''; grid.style.boxShadow=''; }, 1500);
    }
    showToast && showToast('⚠ Select at least one room to begin!');
    return;
  }

  const difficulty = document.querySelector('.diff-btn.active')?.dataset.diff || 'medium';
  const user       = JSON.parse(localStorage.getItem('cer_user') || 'null');
  const name       = user?.username || user?.name || 'AGENT';

  // Store session data
  sessionStorage.setItem('cer_player',       name);
  sessionStorage.setItem('cer_diff',         difficulty);
  sessionStorage.setItem('cer_room_ids',     JSON.stringify([...selectedRooms]));

  incrementAttempts();

  const btn = document.getElementById('startBtn');
  btn.innerHTML = '<span class="btn-glitch" data-text="LAUNCHING...">LAUNCHING...</span>';
  btn.style.pointerEvents = 'none';
  document.getElementById('statStatus').textContent = '🟡 BREACHING';
  document.getElementById('statStatus').classList.remove('blink-red');

  setTimeout(() => { window.location.href = 'game.html'; }, 50);
}


// ── VAULT ITEM HOVER SOUNDS (optional visual) ─
document.querySelectorAll('.vault-item').forEach(item => {
  item.addEventListener('mouseenter', () => {
    item.style.borderColor = 'rgba(0,255,65,0.5)';
  });
  item.addEventListener('mouseleave', () => {
    item.style.borderColor = '';
  });
});


// ── EXPOSE saveScore GLOBALLY for game.html ──
window.saveScore = saveScore;
window.incrementEscapes = incrementEscapes;
