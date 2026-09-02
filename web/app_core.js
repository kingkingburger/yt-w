/* yt-w operator console client. */
const API = '';
const state = {
  activeTab: 'youtube-upload',
  files: [],
  selectedPaths: new Set(),
  sequence: [],
  sequenceViewMode: 'compact',
  sourceGroupOpen: new Set(),
  sourceGroups: [],
  mergeMode: 'concat',
  mergeJobs: [],
  mergeDownloadDirectory: null,
  savingMergeJobs: new Set(),
  splitSelectedPath: null,
  splitStrategy: 'interval',
  splitJobs: [],
  splitSearchQuery: '',
  splitGroupOpen: new Set(),
  splitGroups: [],
  youtubeUploadSelectedPath: null,
  youtubeUploadJobs: [],
  youtubeOAuthStatus: null,
  dlFormat: 'video',
  pendingChannelDelete: null,
  recentFiles: [],
  recentRecordings: [],
  bootTime: null,
};

const YOUTUBE_MUTATION_HEADERS = Object.freeze({
  'X-YT-Monitor-Request': '1',
});

/* ── helpers ───────────────────────────────────────────────────────── */
const $ = (id) => document.getElementById(id);
const fmtBytes = (n) => {
  if (!n && n !== 0) return '─';
  const u = ['B','KB','MB','GB','TB'];
  let i = 0; while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(n < 10 && i > 0 ? 1 : 0)}${u[i]}`;
};
const fmtDuration = (sec) => {
  if (sec == null) return '─';
  sec = Math.max(0, Math.floor(sec));
  const d = Math.floor(sec / 86400);
  const h = Math.floor((sec % 86400) / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  if (d > 0) return `${d}일 ${h}시간`;
  if (h > 0) return `${h}시간 ${String(m).padStart(2,'0')}분`;
  if (m > 0) return `${m}분 ${String(s).padStart(2,'0')}초`;
  return `${s}초`;
};
const fmtAge = (mtime) => {
  if (!mtime) return '─';
  const sec = Math.max(0, Math.floor(Date.now() / 1000 - mtime));
  return fmtDuration(sec) + ' 전';
};
const fmtClock = (d = new Date()) =>
  [d.getHours(), d.getMinutes(), d.getSeconds()]
    .map(n => String(n).padStart(2, '0')).join(':');
const escapeHtml = (s) => {
  const div = document.createElement('div');
  div.textContent = s ?? '';
  return div.innerHTML;
};
const escapeHtmlAttribute = (s) => String(s ?? '')
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;')
  .replace(/'/g, '&#39;');
const initial = (name) => {
  const c = (name || '').trim().charAt(0);
  return c ? c.toUpperCase() : '·';
};
const JOB_STATE_LABELS = {
  queued:    ['차례 기다리는 중', 'dim'],
  running:   ['진행 중',         'amber'],
  done:      ['완료',            'ok'],
  failed:    ['실패',            'err'],
  cancelled: ['취소됨',          'warn'],
};
const jobStateChip = (status) => {
  const [label, kind] = JOB_STATE_LABELS[status] || [status, 'dim'];
  return `<span class="chip ${kind}">${label}</span>`;
};
const emptyState = ({ icon, title, sub, action = '' }) => `<div class="empty">
  <div class="empty-icon">${icon}</div>
  <div class="empty-title">${title}</div>
  <div class="empty-sub">${sub}</div>
  ${action}
</div>`;
/* 목록을 못 불러온 상태와 목록이 비어 있는 상태는 다르다. 실패를 빈 상태로 그리면
   화면이 "아직 없어요"라고 거짓말하고, 운영자는 결국 탐색기를 열어 확인하게 된다. */
const renderLoadFailure = (hostId, title, error) => {
  const host = $(hostId);
  if (!host) return;
  host.innerHTML = `<div class="empty">
  <div class="empty-icon empty-icon-alert">!</div>
  <div class="empty-title">${escapeHtml(title)}</div>
  <div class="empty-sub">${escapeHtml(error?.message || '잠시 후 다시 시도해 주세요')}</div>
</div>`;
};
const throwIfResponseFailed = async (response, fallbackMessage = '요청을 처리하지 못했습니다') => {
  if (response.ok) return;
  const payload = await response.json().catch(() => ({}));
  throw new Error(payload.detail || fallbackMessage);
};

/* ── tabs ──────────────────────────────────────────────────────────── */
function switchTab(tab) {
  state.activeTab = tab;
  document.querySelectorAll('.nav-btn').forEach(b => {
    const isActive = b.dataset.tab === tab;
    b.classList.toggle('active', isActive);
    // tablist 안에서는 활성 탭만 Tab 키 순서에 남고, 나머지는 화살표로 옮겨 다닌다.
    b.setAttribute('aria-selected', isActive ? 'true' : 'false');
    b.tabIndex = isActive ? 0 : -1;
  });
  document.querySelectorAll('.panel').forEach(p =>
    p.classList.toggle('active', p.id === `panel-${tab}`));
  if (tab === 'merge') { loadFiles(); loadJobs(); }
  if (tab === 'split') { loadFiles(); loadSplitJobs(); }
  if (tab === 'youtube-upload') {
    loadFiles();
    loadYouTubeOAuthStatus();
    loadYouTubeUploadJobs();
  }
  if (tab === 'monitor') { loadChannels(); loadRecentRecordings(); }
  if (tab === 'download') {
    loadRecentFiles();
    setTimeout(() => $('url-input')?.focus(), 50);
  }
}

/* 좌우/홈엔드로 탭을 옮긴다. tablist의 기본 키보드 규약. */
function handleTabKeydown(event) {
  const keys = ['ArrowRight', 'ArrowDown', 'ArrowLeft', 'ArrowUp', 'Home', 'End'];
  if (!keys.includes(event.key)) return;
  const buttons = [...document.querySelectorAll('.nav-btn')];
  const current = buttons.findIndex(b => b.dataset.tab === state.activeTab);
  if (current < 0) return;
  const last = buttons.length - 1;
  let next = current;
  if (event.key === 'ArrowRight' || event.key === 'ArrowDown') next = current === last ? 0 : current + 1;
  if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') next = current === 0 ? last : current - 1;
  if (event.key === 'Home') next = 0;
  if (event.key === 'End') next = last;
  event.preventDefault();
  switchTab(buttons[next].dataset.tab);
  buttons[next].focus();
}

/* ── boot / clock / system status ──────────────────────────────────── */
$('boot-host').textContent = location.hostname || 'localhost';
$('boot-port').textContent = location.port || '80';
setInterval(() => $('boot-time').textContent = fmtClock(), 1000);
$('boot-time').textContent = fmtClock();

function setDot(dotId, kind) {
  const el = $(dotId);
  if (!el) return;
  el.classList.remove('ok', 'warn', 'err');
  if (kind) el.classList.add(kind);
}

async function systemRefresh() {
  try {
    const res = await fetch(`${API}/api/system/status`);
    if (!res.ok) return;
    const s = await res.json();
    state.bootTime = s.boot_time;

    $('boot-uptime').textContent = fmtDuration(s.uptime_seconds);
    $('boot-dlpath').textContent = s.downloads.directory;
    $('boot-files').textContent = s.downloads.file_count.toLocaleString();

    const isRunning = s.monitor.is_running;
    const monitorState = s.monitor.state || 'missing';
    const monitorAge = s.monitor.age_seconds;
    const monitorLabel = isRunning
      ? `녹화 감시 중 · ${s.monitor.active_channels}/${s.monitor.total_channels}`
      : monitorState === 'missing'
        ? 'yt-monitor 신호 없음'
        : monitorState === 'stopped'
          ? 'yt-monitor 중지됨'
          : 'yt-monitor 확인 필요';
    setDot('sys-monitor-dot', isRunning ? 'ok' : (monitorState === 'missing' ? 'err' : 'warn'));
    $('stat-monitor-val').textContent = monitorLabel;

    setDot('sys-discord-dot', s.discord_enabled ? 'ok' : 'warn');
    $('stat-discord-val').textContent = s.discord_enabled ? '연결됨' : '미설정';
    $('stat-discord-val').classList.toggle('dim', !s.discord_enabled);
    const discordText = $('discord-state-text');
    discordText.textContent = s.discord_enabled
      ? '웹후크가 연결돼 있어 라이브 감지·다운로드 완료·오류 알림이 디스코드로 갑니다.'
      : 'DISCORD_WEBHOOK_URL이 비어 있습니다. .env에 웹후크 주소를 넣고 컨테이너를 다시 시작하세요.';
    discordText.classList.toggle('go', s.discord_enabled);

    const used = s.disk.used_bytes;
    const total = s.disk.total_bytes;
    const pct = total > 0 ? Math.round(used / total * 100) : 0;
    const dlSize = s.downloads.total_size_bytes;
    $('stat-disk-val').textContent = total > 0 ? `${fmtBytes(used)} / ${fmtBytes(total)}` : '─';
    $('stat-disk-sub').textContent = `${pct}% 사용 · 다운로드 ${fmtBytes(dlSize)}`;
    const dKind = pct >= 92 ? 'err' : pct >= 80 ? 'warn' : 'ok';
    setDot('sys-disk-dot', dKind);

    const heroEl = $('monitor-hero');
    if (heroEl) heroEl.classList.toggle('running', isRunning);
    $('tile-monitor-state').innerHTML = isRunning ? '<em>녹화 감시 중</em>' : '데몬 상태 확인';
    $('tile-monitor-state-sub').textContent = isRunning
      ? `${s.monitor.active_channels}개 채널을 yt-monitor 컨테이너에서 확인하고 있어요`
      : monitorState === 'missing'
        ? 'yt-monitor 컨테이너 heartbeat가 아직 없습니다'
        : `마지막 신호 ${fmtDuration(monitorAge || 0)} 전 · ${s.monitor.message || monitorState}`;
    $('tile-active').textContent = s.monitor.active_channels;
    $('tile-total').textContent = s.monitor.total_channels;
    $('tile-uptime').textContent = fmtDuration(s.uptime_seconds);
  } catch (e) { /* silent */ }
}

/* ── cookie ────────────────────────────────────────────────────────── */
async function checkCookie() {
  try {
    const r = await fetch(`${API}/api/cookie/status`);
    const c = await r.json();
    setDot('sys-cookie-dot', c.valid ? 'ok' : 'err');
    $('stat-cookie-val').textContent = c.valid ? '정상' : '만료';
    $('stat-cookie-val').classList.toggle('dim', false);
  } catch (e) {}
}
