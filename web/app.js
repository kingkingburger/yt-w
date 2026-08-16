/* yt-w operator console client. */
const API = '';
const state = {
  activeTab: 'merge',
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

/* ── tabs ──────────────────────────────────────────────────────────── */
function switchTab(tab) {
  state.activeTab = tab;
  document.querySelectorAll('.nav-btn').forEach(b =>
    b.classList.toggle('active', b.dataset.tab === tab));
  document.querySelectorAll('.panel').forEach(p =>
    p.classList.toggle('active', p.id === `panel-${tab}`));
  if (tab === 'merge') { loadFiles(); loadJobs(); }
  if (tab === 'split') { loadFiles(); loadSplitJobs(); }
  if (tab === 'youtube-upload') {
    loadFiles();
    loadYouTubeOAuthStatus();
    loadYouTubeUploadJobs();
  }
  if (tab === 'channels' || tab === 'monitor') { loadChannels(); }
  if (tab === 'download') { setTimeout(() => $('url-input')?.focus(), 50); }
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

/* ── monitor / channels ────────────────────────────────────────────── */
async function loadChannels() {
  try {
    const r = await fetch(`${API}/api/channels`);
    const channels = await r.json();
    renderChannelTable(channels);
    renderMonitorChannelList(channels);
  } catch (e) {}
}

function renderChannelTable(channels) {
  const host = $('channel-table');
  if (!channels.length) {
    host.innerHTML = `
      <div class="empty">
        <div class="empty-icon">+</div>
        <div class="empty-title">아직 등록된 채널이 없어요</div>
        <div class="empty-sub">유튜브 채널을 추가하면 라이브 시작 시 자동으로 녹화돼요</div>
        <button class="btn primary" onclick="openAddChannelModal()">+ 첫 채널 추가하기</button>
      </div>`;
    return;
  }
  host.innerHTML = `
    <table class="table">
      <thead><tr>
        <th class="col-num">#</th>
        <th>이름</th>
        <th>URL</th>
        <th>상태</th>
        <th></th>
      </tr></thead>
      <tbody>
        ${channels.map((c, i) => `
          <tr>
            <td class="col-num">${String(i + 1).padStart(2, '0')}</td>
            <td><span class="ch-name">${escapeHtml(c.name)}</span></td>
            <td><span class="ch-url">${escapeHtml(c.url)}</span></td>
            <td><span class="chip ${c.enabled ? 'ok' : 'dim'}">${c.enabled ? '활성' : '비활성'}</span></td>
            <td>
              <div class="actions">
                <button class="btn sm" onclick="toggleChannel('${c.id}', ${!c.enabled})">${c.enabled ? '비활성화' : '활성화'}</button>
                <button class="btn sm danger" onclick="deleteChannel('${c.id}', '${escapeHtml(c.name).replace(/'/g, "\\'")}')">삭제</button>
              </div>
            </td>
          </tr>
        `).join('')}
      </tbody>
    </table>`;
}

function renderMonitorChannelList(channels) {
  const host = $('monitor-channel-list');
  if (!channels.length) {
    host.innerHTML = `
      <div class="empty">
        <div class="empty-icon">+</div>
        <div class="empty-title">감시할 채널이 없어요</div>
        <div class="empty-sub">먼저 유튜브 채널을 등록해야 자동 녹화를 시작할 수 있어요</div>
        <button class="btn primary" onclick="openAddChannelModal()">+ 채널 추가하기</button>
      </div>`;
    return;
  }
  host.innerHTML = `
    <div class="channel-list">
      ${channels.map((c) => `
        <div class="channel-row">
          <div class="channel-avatar">${escapeHtml(initial(c.name))}</div>
          <div class="channel-info">
            <div class="channel-name">${escapeHtml(c.name)}</div>
            <div class="channel-url">${escapeHtml(c.url)}</div>
          </div>
          <span class="chip ${c.enabled ? 'ok' : 'dim'}">${c.enabled ? '감시 중' : '일시중지'}</span>
          <button class="btn sm" onclick="toggleChannel('${c.id}', ${!c.enabled})">${c.enabled ? '일시중지' : '감시 시작'}</button>
        </div>
      `).join('')}
    </div>`;
}

function openAddChannelModal() { $('add-channel-overlay').classList.add('active'); setTimeout(() => $('channel-name')?.focus(), 50); }
function closeAddChannelModal() {
  $('add-channel-overlay').classList.remove('active');
  $('channel-name').value = ''; $('channel-url').value = '';
}
async function addChannel(e) {
  e.preventDefault();
  const name = $('channel-name').value, url = $('channel-url').value;
  try {
    const r = await fetch(`${API}/api/channels`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, url, enabled: true }),
    });
    if (!r.ok) { const e = await r.json(); throw new Error(e.detail); }
    notify('완료', `'${name}' 채널을 추가했어요`, 'ok');
    closeAddChannelModal(); loadChannels(); systemRefresh();
  } catch (e) { notify('오류', e.message, 'err'); }
}
async function toggleChannel(id, enabled) {
  try {
    const r = await fetch(`${API}/api/channels/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled }),
    });
    if (!r.ok) { const e = await r.json(); throw new Error(e.detail); }
    notify('완료', `채널을 ${enabled ? '활성화' : '비활성화'}했어요`, 'ok');
    loadChannels(); systemRefresh();
  } catch (e) { notify('오류', e.message, 'err'); }
}
async function deleteChannel(id, name) {
  if (!confirm(`'${name}' 채널을 삭제할까요?`)) return;
  try {
    const r = await fetch(`${API}/api/channels/${id}`, { method: 'DELETE' });
    if (!r.ok) { const e = await r.json(); throw new Error(e.detail); }
    notify('완료', `'${name}' 채널을 삭제했어요`, 'ok');
    loadChannels(); systemRefresh();
  } catch (e) { notify('오류', e.message, 'err'); }
}

/* ── discord test ──────────────────────────────────────────────────── */
async function testDiscord() {
  try {
    const r = await fetch(`${API}/api/system/discord/test`, { method: 'POST' });
    const d = await r.json();
    if (d.sent) notify('완료', '디스코드로 테스트 메시지를 보냈어요', 'ok');
    else notify('오류', `디스코드 발송 실패: ${d.reason || '알 수 없는 이유'}`, 'err');
  } catch (e) { notify('오류', '디스코드 테스트 실패', 'err'); }
}

/* ── merge :: file list ────────────────────────────────────────────── */
async function loadFiles(refresh = false) {
  try {
    const query = refresh ? '?refresh=true' : '';
    const r = await fetch(`${API}/api/files${query}`);
    state.files = await r.json();
    const validPaths = new Set(state.files.map(f => f.path));
    state.selectedPaths = new Set(
      [...state.selectedPaths].filter(path => validPaths.has(path))
    );
    state.sequence = state.sequence.filter(path => validPaths.has(path));
    if (!validPaths.has(state.splitSelectedPath)) state.splitSelectedPath = null;
    if (!validPaths.has(state.youtubeUploadSelectedPath)) state.youtubeUploadSelectedPath = null;
    renderFileList();
    renderSequence();
    renderSplitFileList();
    renderSplitSelection();
    renderYouTubeUploadFileList();
    renderYouTubeUploadReady();
  } catch (e) {}
}
function renderFileList() {
  const host = $('merge-file-list');
  const sourceFiles = availableSourceFiles();
  $('merge-file-count').textContent = `${sourceFiles.length}개`;
  const selectAllBtn = $('btn-select-all');
  const deselectAllBtn = $('btn-deselect-all');
  if (selectAllBtn) selectAllBtn.disabled = sourceFiles.length === 0;
  if (deselectAllBtn) deselectAllBtn.disabled = state.sequence.length === 0;
  if (!state.files.length) {
    host.innerHTML = `
      <div class="empty">
        <div class="empty-icon">⌘</div>
        <div class="empty-title">아직 받아둔 영상이 없어요</div>
        <div class="empty-sub">다운로드 탭에서 영상을 받거나, 라이브 녹화가 채널을 녹화하면 여기에 쌓입니다</div>
        <button class="btn primary" type="button" onclick="switchTab('download')">다운로드 탭으로 가기</button>
      </div>`;
    return;
  }
  if (!sourceFiles.length) {
    state.sourceGroups = [];
    host.innerHTML = `
      <div class="empty">
        <div class="empty-icon empty-icon-check" aria-hidden="true"></div>
        <div class="empty-title">고를 영상이 더 없어요</div>
        <div class="empty-sub">받아둔 영상을 모두 오른쪽 순서에 넣었습니다</div>
      </div>`;
    return;
  }
  state.sourceGroups = buildFileGroups(sourceFiles);
  host.innerHTML = state.sourceGroups.map((group, groupIdx) => {
    const open = state.sourceGroupOpen.has(group.id);
    const selectedCount = group.paths.filter(path => state.selectedPaths.has(path)).length;
    const allSelected = selectedCount === group.paths.length;
    const someSelected = selectedCount > 0 && !allSelected;
    const partBadge = group.partLabel ? `<span class="part-chip">${escapeHtml(group.partLabel)}</span>` : '';
    return `
      <div class="file-group ${open ? 'open' : ''} ${allSelected ? 'selected' : ''}">
        <div class="file-group-head"
             draggable="true"
             ondragstart="sourceGroupDragStart(event, ${groupIdx})"
             ondragend="fileDragEnd(event)"
             onclick="toggleSourceGroup(${groupIdx})">
          <span class="tree-toggle" aria-hidden="true">▸</span>
          <span class="selection-control selection-checkbox">
            <input type="checkbox"
                   aria-label="${escapeHtml(group.name)} 전체 선택"
                   ${allSelected ? 'checked' : ''}
                   ${someSelected ? 'data-partial="true"' : ''}
                   onclick="event.stopPropagation()"
                   onchange="toggleSourceGroupSelect(${groupIdx}, this.checked)" />
            <span class="selection-mark" aria-hidden="true"></span>
          </span>
          <div class="file-group-title" title="${escapeHtml(group.name)}">${escapeHtml(group.name)}</div>
          <div class="file-group-tools">
            ${partBadge}
            <div class="file-meta nowrap">${group.paths.length}개 · ${fmtBytes(group.paths.reduce((sum, path) => sum + sizeOfPath(path), 0))}</div>
            <button type="button" class="btn danger sm file-delete-btn" draggable="false"
                    title="${escapeHtml(group.name)} 그룹 전체 삭제"
                    aria-label="${escapeHtml(group.name)} 그룹 전체 삭제"
                    onclick="deleteSourceGroup(${groupIdx}, event)">✕</button>
          </div>
        </div>
        <div class="file-group-children">
          ${group.files.map(file => renderSourceFileRow(file)).join('')}
        </div>
      </div>`;
  }).join('');
  document.querySelectorAll('input[data-partial="true"]').forEach(input => {
    input.indeterminate = true;
  });
}
function renderSourceFileRow(f) {
  const fname = mergeFileName(f.path);
  const checked = state.selectedPaths.has(f.path);
  const safePath = escapeHtml(f.path).replace(/'/g, "\\'");
  return `
    <label class="file-row child ${checked ? 'selected' : ''}"
           draggable="true"
           data-path="${escapeHtml(f.path)}"
           ondragstart="fileDragStart(event, '${safePath}')"
           ondragend="fileDragEnd(event)">
      <span class="selection-control selection-checkbox">
        <input type="checkbox" aria-label="${escapeHtml(fname)} 선택" ${checked ? 'checked' : ''}
               onchange="toggleFileSelect('${safePath}', this.checked)" />
        <span class="selection-mark" aria-hidden="true"></span>
      </span>
      <span class="file-grip" aria-hidden="true">::</span>
      <div class="file-name" title="${escapeHtml(fname)}">${escapeHtml(fname)}</div>
      <div class="file-meta nowrap">${fmtBytes(f.size_bytes)}</div>
      <div class="file-meta nowrap">${fmtAge(f.mtime)}</div>
      <button type="button" class="btn danger sm file-delete-btn" draggable="false"
              title="${escapeHtml(fname)} 삭제"
              aria-label="${escapeHtml(fname)} 삭제"
              onclick="deleteSourceFile('${safePath}', event)">✕</button>
    </label>`;
}
async function deleteSourceFiles(paths, label) {
  const uniquePaths = [...new Set((paths || []).filter(Boolean))];
  if (!uniquePaths.length) return;
  const target = uniquePaths.length === 1
    ? `"${label || uniquePaths[0]}" 파일`
    : `"${label || '선택한 그룹'}"의 소스 파일 ${uniquePaths.length}개`;
  if (!confirm(`${target}를 삭제할까요?\n삭제한 파일은 복구할 수 없습니다.`)) return;

  try {
    const response = await fetch(`${API}/api/files`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ paths: uniquePaths }),
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(result.detail || '파일 삭제에 실패했습니다');
    await loadFiles(true);
    systemRefresh();
    notify('삭제 완료', `소스 파일 ${result.count}개를 삭제했습니다`, 'ok');
  } catch (error) {
    notify('오류', error.message || '파일 삭제에 실패했습니다', 'err');
  }
}
function deleteSourceFile(path, event) {
  event?.preventDefault();
  event?.stopPropagation();
  deleteSourceFiles([path], mergeFileName(path));
}
function deleteSourceGroup(groupIdx, event) {
  event?.preventDefault();
  event?.stopPropagation();
  const group = state.sourceGroups[groupIdx];
  if (group) deleteSourceFiles(group.paths, group.name);
}
function toggleSourceGroup(groupIdx) {
  const group = state.sourceGroups[groupIdx];
  if (!group) return;
  if (state.sourceGroupOpen.has(group.id)) state.sourceGroupOpen.delete(group.id);
  else state.sourceGroupOpen.add(group.id);
  renderFileList();
}
function toggleSourceGroupSelect(groupIdx, on) {
  const group = state.sourceGroups[groupIdx];
  if (!group) return;
  if (on) {
    addPathsToSequence(group.paths);
  } else {
    group.paths.forEach(path => state.selectedPaths.delete(path));
    state.sequence = state.sequence.filter(path => !group.paths.includes(path));
    refreshDefaultMergeOutputName();
    renderFileList();
    renderSequence();
  }
}
function toggleFileSelect(path, on) {
  if (on) {
    state.selectedPaths.add(path);
    if (!state.sequence.includes(path)) state.sequence.push(path);
  } else {
    state.selectedPaths.delete(path);
    state.sequence = state.sequence.filter(p => p !== path);
  }
  refreshDefaultMergeOutputName();
  renderFileList(); renderSequence();
}
function selectAllFiles() {
  const sourceFiles = availableSourceFiles();
  if (!sourceFiles.length) return;
  buildFileGroups(sourceFiles).flatMap(group => group.paths).forEach(path => {
    if (!state.selectedPaths.has(path)) {
      state.selectedPaths.add(path);
      if (!state.sequence.includes(path)) state.sequence.push(path);
    }
  });
  refreshDefaultMergeOutputName();
  renderFileList(); renderSequence();
}
function deselectAllFiles() {
  state.sequence = [];
  state.selectedPaths.clear();
  refreshDefaultMergeOutputName();
  renderFileList(); renderSequence();
}

/* ── merge :: sequence ─────────────────────────────────────────────── */
function splitMergePath(path) {
  const dirIdx = path.lastIndexOf('/');
  return {
    dir: dirIdx >= 0 ? path.slice(0, dirIdx + 1) : '',
    name: dirIdx >= 0 ? path.slice(dirIdx + 1) : path,
  };
}
function mergeFileName(path) {
  return splitMergePath(path).name;
}
function availableSourceFiles(files = state.files, sequence = state.sequence) {
  const inSequence = new Set(sequence);
  return files.filter(file => !inSequence.has(file.path));
}
function sizeOfPath(path) {
  return state.files.find(file => file.path === path)?.size_bytes || 0;
}
function inferPartGroup(prefix) {
  const cleaned = prefix.replace(/[._\-\s]+$/g, '');
  const tokens = cleaned.split(/[._\-\s]+/).filter(Boolean);
  if (tokens.length >= 2) {
    const dateToken = tokens[tokens.length - 2];
    const timeToken = tokens[tokens.length - 1];
    if (/^\d{8}$/.test(dateToken) && /^\d{6}$/.test(timeToken)) {
      return `${dateToken}_${timeToken}`;
    }
  }

  const last = tokens[tokens.length - 1] || cleaned || prefix;
  const hashLike = /^[A-Fa-f0-9]{8,}$/.test(last)
    || (/^[A-Za-z0-9_-]{6,}$/.test(last) && /[A-Za-z]/.test(last) && /\d/.test(last))
    || /^\d{10,}$/.test(last);
  return hashLike ? last : cleaned;
}
function getPartInfo(path) {
  const { dir, name } = splitMergePath(path);
  const match = name.match(/^(.*?)(?:[._\-\s]?part[._\-\s]*)(\d+)(.*)$/i);
  if (!match) return null;
  const number = Number(match[2]);
  if (!Number.isFinite(number)) return null;
  const prefix = match[1];
  const suffix = match[3];
  const group = inferPartGroup(prefix);
  return {
    path,
    dir,
    prefix,
    suffix,
    group,
    /* 묶는 기준(group)은 날짜·시간까지만 좁히지만, 화면에 띄우는 이름은
       접두사 전체를 쓴다. "20260804_210000"만 보여주면 어느 채널의 녹화인지
       알 수 없다. */
    label: prefix.replace(/[._\-\s]+$/g, '') || group,
    number,
    rawNumber: match[2],
    key: `${dir}\u0000${group.toLowerCase()}\u0000${suffix.toLowerCase()}`,
  };
}
function getPartRun(path, filePaths = state.files.map(f => f.path)) {
  const info = getPartInfo(path);
  if (!info) return [path];

  const byNumber = new Map();
  filePaths.forEach(candidate => {
    const candidateInfo = getPartInfo(candidate);
    if (!candidateInfo || candidateInfo.key !== info.key) return;
    if (!byNumber.has(candidateInfo.number)) byNumber.set(candidateInfo.number, candidate);
  });

  let start = info.number;
  while (byNumber.has(start - 1)) start -= 1;
  let end = info.number;
  while (byNumber.has(end + 1)) end += 1;

  const run = [];
  for (let n = start; n <= end; n += 1) {
    const candidate = byNumber.get(n);
    if (!candidate) break;
    run.push(candidate);
  }
  return run.length > 1 ? run : [path];
}
function getPartRunLabel(path, filePaths = state.files.map(f => f.path)) {
  const run = getPartRun(path, filePaths);
  if (run.length < 2) return '';
  const infos = run.map(getPartInfo).filter(Boolean);
  const width = Math.max(...infos.map(info => info.rawNumber.length));
  const nums = infos.map(info => info.number);
  const first = String(Math.min(...nums)).padStart(width, '0');
  const last = String(Math.max(...nums)).padStart(width, '0');
  const label = infos[0]?.label || '';
  return label ? `${label} · part ${first}-${last}` : `part ${first}-${last}`;
}
function getPartRangeLabel(paths) {
  const infos = paths.map(getPartInfo).filter(Boolean);
  if (!infos.length) return '';
  const width = Math.max(...infos.map(info => info.rawNumber.length));
  const nums = infos.map(info => info.number);
  const first = String(Math.min(...nums)).padStart(width, '0');
  const last = String(Math.max(...nums)).padStart(width, '0');
  return `part ${first}-${last}`;
}
function buildFileGroups(files = state.files) {
  const groups = [];
  const byId = new Map();

  files.forEach((file) => {
    const info = getPartInfo(file.path);
    const id = info ? info.key : `file:${file.path}`;
    let group = byId.get(id);
    if (!group) {
      group = {
        id,
        key: info?.key || id,
        name: info?.label || mergeFileName(file.path),
        isPartGroup: Boolean(info),
        files: [],
        paths: [],
      };
      byId.set(id, group);
      groups.push(group);
    }
    group.files.push({ ...file, partInfo: info });
    group.paths.push(file.path);
  });

  groups.forEach((group) => {
    if (!group.isPartGroup) return;
    group.files.sort((a, b) => {
      const byPart = (a.partInfo?.number ?? 0) - (b.partInfo?.number ?? 0);
      return byPart || a.path.localeCompare(b.path, 'ko', { numeric: true, sensitivity: 'base' });
    });
    group.paths = group.files.map(file => file.path);
    group.partLabel = getPartRangeLabel(group.paths);
  });

  return groups;
}
function addPathsToSequence(paths, insertAt = state.sequence.length) {
  const existing = new Set(state.sequence);
  const uniquePaths = [];
  paths.forEach(path => {
    if (existing.has(path)) return;
    existing.add(path);
    uniquePaths.push(path);
  });
  if (!uniquePaths.length) return 0;

  const target = Math.max(0, Math.min(insertAt, state.sequence.length));
  state.sequence.splice(target, 0, ...uniquePaths);
  uniquePaths.forEach(path => state.selectedPaths.add(path));
  refreshDefaultMergeOutputName();
  renderFileList();
  renderSequence();
  return uniquePaths.length;
}
function getSequencePartBlock(idx) {
  const path = state.sequence[idx];
  const info = getPartInfo(path);
  if (!info) return { start: idx, end: idx };

  let start = idx;
  while (start > 0) {
    const prev = getPartInfo(state.sequence[start - 1]);
    const current = getPartInfo(state.sequence[start]);
    if (!prev || !current || prev.key !== info.key || prev.number !== current.number - 1) break;
    start -= 1;
  }

  let end = idx;
  while (end < state.sequence.length - 1) {
    const current = getPartInfo(state.sequence[end]);
    const next = getPartInfo(state.sequence[end + 1]);
    if (!current || !next || next.key !== info.key || next.number !== current.number + 1) break;
    end += 1;
  }

  return { start, end };
}
function moveSequenceBlock(start, end, dropIdx) {
  if (dropIdx >= start && dropIdx <= end + 1) return false;
  const count = end - start + 1;
  const moved = state.sequence.splice(start, count);
  const insertAt = dropIdx > start ? dropIdx - count : dropIdx;
  state.sequence.splice(insertAt, 0, ...moved);
  return true;
}
function buildSequenceRows(mode = state.sequenceViewMode) {
  const rows = [];
  for (let idx = 0; idx < state.sequence.length; idx += 1) {
    const block = mode === 'compact' ? getSequencePartBlock(idx) : { start: idx, end: idx };
    const start = block.start;
    const end = block.end;
    rows.push({
      start,
      end,
      paths: state.sequence.slice(start, end + 1),
    });
    idx = end;
  }
  return rows;
}
function formatPartRangeName(paths) {
  const first = getPartInfo(paths[0]);
  const last = getPartInfo(paths[paths.length - 1]);
  if (!first || !last || first.key !== last.key) return '';
  const width = Math.max(first.rawNumber.length, last.rawNumber.length);
  const firstNum = String(first.number).padStart(width, '0');
  const lastNum = String(last.number).padStart(width, '0');
  return `${first.label} · part ${firstNum}-${lastNum}${first.suffix}`;
}
function sequenceRowName(row) {
  if (row.paths.length === 1) return mergeFileName(row.paths[0]);
  return formatPartRangeName(row.paths)
    || `${mergeFileName(row.paths[0])} - ${mergeFileName(row.paths[row.paths.length - 1])}`;
}
function setSequenceViewMode(mode) {
  state.sequenceViewMode = mode === 'full' ? 'full' : 'compact';
  renderSequence();
}
function renderSequence() {
  const host = $('merge-seq-list');
  host.ondragover = seqListDragOver;
  host.ondragleave = seqListDragLeave;
  host.ondrop = seqListDrop;
  const rows = buildSequenceRows();
  $('merge-seq-count').textContent = state.sequenceViewMode === 'compact' && rows.length !== state.sequence.length
    ? `${state.sequence.length}개 클립 · ${rows.length}줄`
    : `${state.sequence.length}개 클립`;
  const compactBtn = $('seq-view-compact');
  const fullBtn = $('seq-view-full');
  if (compactBtn) compactBtn.classList.toggle('active', state.sequenceViewMode === 'compact');
  if (fullBtn) fullBtn.classList.toggle('active', state.sequenceViewMode === 'full');
  const sortBtn = $('btn-sort-sequence-name');
  if (sortBtn) sortBtn.disabled = state.sequence.length < 2;
  renderMergeStrip();
  renderMergeReady();
  if (!state.sequence.length) {
    host.classList.add('empty-seq');
    host.innerHTML = '왼쪽 목록에서 영상을 고르면 고른 순서대로 여기에 쌓입니다.<br />끌어서 순서를 바꿀 수 있어요.';
    return;
  }
  host.classList.remove('empty-seq');
  host.innerHTML = rows.map((row) => {
    const fname = sequenceRowName(row);
    const blockSize = row.end - row.start + 1;
    const blockLabel = blockSize > 1 ? getPartRunLabel(row.paths[0], row.paths) : '';
    const blockBadge = blockLabel ? `<span class="seq-badge">${escapeHtml(blockLabel)}</span>` : '';
    const idxLabel = blockSize > 1
      ? `${String(row.start + 1).padStart(2, '0')}-${String(row.end + 1).padStart(2, '0')}`
      : String(row.start + 1).padStart(2, '0');
    const title = row.paths.map(mergeFileName).join('\n');
    const removeAction = blockSize > 1
      ? `removeSeqBlock(${row.start}, ${row.end})`
      : `removeSeqItem(${row.start})`;
    return `
      <div class="seq-item ${blockSize > 1 ? 'part-block' : ''}" draggable="true" data-idx="${row.start}"
           ondragstart="seqDragStart(event, ${row.start})"
           ondragover="seqDragOver(event, ${row.start})"
           ondragleave="seqDragLeave(event, ${row.start})"
           ondrop="seqDrop(event, ${row.start})"
           ondragend="seqDragEnd(event)">
        <div class="grip">⋮⋮</div>
        <div class="idx">${idxLabel}</div>
        <div class="name" title="${escapeHtml(title)}">${escapeHtml(fname)}${blockBadge}</div>
        <button class="btn sm danger" aria-label="${escapeHtml(fname)} 목록에서 빼기"
                onclick="${removeAction}">✕</button>
      </div>`;
  }).join('');
}

/* ── merge :: 결과 미리보기 스트립 ─────────────────────────────────── */
/* 조각을 하나로 붙이는 게 이 화면의 본론이라, 실행 전에 결과를 한 줄로 본다.
   폭은 용량 비율이다. 재생 길이는 서버가 알려주지 않으므로 그렇게 표기한다. */
function renderMergeStrip() {
  const track = $('merge-strip-track');
  const total = $('merge-strip-total');
  const note = $('merge-strip-note');
  if (!track) return;

  const totalBytes = state.sequence.reduce((sum, path) => sum + sizeOfPath(path), 0);
  if (!state.sequence.length) {
    track.className = 'strip-track empty';
    track.textContent = '고른 영상이 여기에 순서대로 이어 붙습니다';
    total.textContent = '클립 없음';
    note.style.display = 'none';
    return;
  }

  note.style.display = '';
  total.textContent = `${state.sequence.length}개 클립 · ${fmtBytes(totalBytes)}`;
  track.className = 'strip-track';
  track.innerHTML = state.sequence.map((path, index) => {
    const bytes = sizeOfPath(path);
    const share = totalBytes > 0 ? bytes / totalBytes : 1 / state.sequence.length;
    const label = String(index + 1).padStart(2, '0');
    return `
      <div class="strip-block" style="flex: ${Math.max(share, 0.001)} 1 0"
           title="${escapeHtml(mergeFileName(path))} · ${fmtBytes(bytes)}"
           onmouseenter="highlightSeqIndex(${index}, true)"
           onmouseleave="highlightSeqIndex(${index}, false)">${label}</div>`;
  }).join('');
}
function highlightSeqIndex(index, on) {
  const rows = buildSequenceRows();
  const row = rows.find(item => index >= item.start && index <= item.end);
  if (!row) return;
  document.querySelector(`.seq-item[data-idx="${row.start}"]`)?.classList.toggle('hot', on);
}

/* ── merge :: 실행 준비 상태 ───────────────────────────────────────── */
/* 못 누르는 이유를 버튼을 누르기 전에 말한다. */
function renderMergeReady() {
  const bar = $('merge-ready');
  const text = $('merge-ready-text');
  const button = $('btn-execute-merge');
  const stepNo = $('merge-step-no');
  if (!bar || !text || !button) return;

  const outputName = ($('merge-output')?.value || '').trim();
  const totalBytes = state.sequence.reduce((sum, path) => sum + sizeOfPath(path), 0);
  const modeLabel = state.mergeMode === 'concat' ? '빠르게' : '재인코딩';

  let blockedReason = '';
  if (state.sequence.length === 0) blockedReason = '합치려면 왼쪽에서 영상을 2개 이상 골라 주세요.';
  else if (state.sequence.length === 1) blockedReason = '영상이 1개뿐입니다. 하나 더 고르면 합칠 수 있어요.';
  else if (!outputName) blockedReason = '저장할 파일 이름을 입력해 주세요.';

  button.disabled = Boolean(blockedReason);
  bar.classList.toggle('go', !blockedReason);
  if (stepNo) stepNo.classList.toggle('done', !blockedReason);
  text.innerHTML = blockedReason
    ? escapeHtml(blockedReason)
    : `${state.sequence.length}개 클립 ${fmtBytes(totalBytes)}를 <strong>${escapeHtml(outputName)}</strong> 하나로 ${modeLabel} 합칩니다.`;
}
function clearSequence() {
  deselectAllFiles();
}
function removeSeqItem(idx) {
  removeSeqBlock(idx, idx);
}
function removeSeqBlock(start, end) {
  const count = end - start + 1;
  const removed = state.sequence.splice(start, count);
  removed.forEach(path => state.selectedPaths.delete(path));
  refreshDefaultMergeOutputName();
  renderFileList(); renderSequence();
}
function sortSequenceByName() {
  state.sequence.sort((a, b) => {
    const aName = a.split('/').pop() || a;
    const bName = b.split('/').pop() || b;
    const byName = aName.localeCompare(bName, 'ko', { numeric: true, sensitivity: 'base' });
    return byName || a.localeCompare(b, 'ko', { numeric: true, sensitivity: 'base' });
  });
  renderSequence();
}
let dragSrc = null;
let mergeDrag = null;
function clearMergeDragUi() {
  document.querySelectorAll('.seq-item').forEach(el => {
    el.classList.remove('dragging', 'drop-target', 'moving-block');
  });
  document.querySelectorAll('.file-row').forEach(el => el.classList.remove('dragging'));
  document.querySelectorAll('.file-group').forEach(el => el.classList.remove('dragging'));
  document.querySelectorAll('.seq-list').forEach(el => el.classList.remove('drop-ready'));
}
function fileDragStart(e, path) {
  const paths = getPartRun(path);
  mergeDrag = { type: 'file', paths };
  dragSrc = null;
  e.currentTarget.classList.add('dragging');
  e.dataTransfer.effectAllowed = 'copyMove';
  e.dataTransfer.setData('text/plain', paths.join('\n'));
}
function sourceGroupDragStart(e, groupIdx) {
  const group = state.sourceGroups[groupIdx];
  if (!group) return;
  mergeDrag = { type: 'file', paths: [...group.paths] };
  dragSrc = null;
  e.currentTarget.closest('.file-group')?.classList.add('dragging');
  e.dataTransfer.effectAllowed = 'copyMove';
  e.dataTransfer.setData('text/plain', group.paths.join('\n'));
}
function fileDragEnd() {
  clearMergeDragUi();
  mergeDrag = null;
}
function seqDragStart(e, idx) {
  const block = getSequencePartBlock(idx);
  dragSrc = idx;
  mergeDrag = {
    type: 'sequence',
    start: block.start,
    end: block.end,
    paths: state.sequence.slice(block.start, block.end + 1),
  };
  e.currentTarget.classList.add('dragging');
  document.querySelectorAll('.seq-item').forEach((el) => {
    const itemIdx = Number(el.dataset.idx);
    if (itemIdx >= block.start && itemIdx <= block.end) el.classList.add('moving-block');
  });
  e.dataTransfer.effectAllowed = 'move';
  e.dataTransfer.setData('text/plain', mergeDrag.paths.join('\n'));
}
function seqDragOver(e, idx) {
  e.preventDefault();
  e.stopPropagation();
  e.dataTransfer.dropEffect = mergeDrag?.type === 'file' ? 'copy' : 'move';
  const inMovingBlock = mergeDrag?.type === 'sequence'
    && idx >= mergeDrag.start
    && idx <= mergeDrag.end;
  if (!inMovingBlock) e.currentTarget.classList.add('drop-target');
}
function seqDragLeave(e) { e.currentTarget.classList.remove('drop-target'); }
function seqDrop(e, idx) {
  e.preventDefault();
  e.stopPropagation();
  if (!mergeDrag) return;

  if (mergeDrag.type === 'file') {
    addPathsToSequence(mergeDrag.paths, idx);
  } else if (mergeDrag.type === 'sequence') {
    if (moveSequenceBlock(mergeDrag.start, mergeDrag.end, idx)) renderSequence();
  }
  clearMergeDragUi();
  mergeDrag = null;
  dragSrc = null;
}
function seqListDragOver(e) {
  if (!mergeDrag) return;
  e.preventDefault();
  e.dataTransfer.dropEffect = mergeDrag.type === 'file' ? 'copy' : 'move';
  e.currentTarget.classList.add('drop-ready');
}
function seqListDragLeave(e) {
  if (!e.currentTarget.contains(e.relatedTarget)) e.currentTarget.classList.remove('drop-ready');
}
function seqListDrop(e) {
  e.preventDefault();
  if (!mergeDrag || e.target.closest('.seq-item')) return;

  if (mergeDrag.type === 'file') {
    addPathsToSequence(mergeDrag.paths);
  } else if (mergeDrag.type === 'sequence') {
    if (moveSequenceBlock(mergeDrag.start, mergeDrag.end, state.sequence.length)) renderSequence();
  }
  clearMergeDragUi();
  mergeDrag = null;
  dragSrc = null;
}
function seqDragEnd() {
  clearMergeDragUi();
  mergeDrag = null;
  dragSrc = null;
}

/* ── merge :: execute ──────────────────────────────────────────────── */
function setMergeMode(mode) {
  state.mergeMode = mode;
  $('mode-concat').classList.toggle('active', mode === 'concat');
  $('mode-reencode').classList.toggle('active', mode === 'reencode');
  renderMergeReady();
}

function supportsMergeDownloadDirectory() {
  return window.isSecureContext
    && typeof window.showDirectoryPicker === 'function'
    && Boolean(window.indexedDB);
}

function renderMergeDownloadDirectory() {
  const path = $('merge-download-directory');
  const note = $('merge-download-directory-note');
  const button = $('btn-merge-download-directory');
  if (!supportsMergeDownloadDirectory()) {
    path.textContent = '지원하지 않는 브라우저';
    note.textContent = 'Chrome 또는 Edge의 HTTPS/localhost 환경에서 사용할 수 있습니다.';
    button.disabled = true;
    return;
  }

  const handle = state.mergeDownloadDirectory;
  path.textContent = handle ? handle.name : '선택되지 않음';
  // 정상 동작 중에는 안내를 띄우지 않는다. 위 분기의 미지원 안내만 남긴다.
  note.textContent = '';
  button.textContent = handle ? '폴더 변경' : '폴더 선택';
}

async function restoreMergeDownloadDirectory() {
  if (!supportsMergeDownloadDirectory()) {
    renderMergeDownloadDirectory();
    return;
  }
  try {
    const handle = await loadMergeDownloadDirectoryHandle(window.indexedDB);
    if (handle?.kind === 'directory') state.mergeDownloadDirectory = handle;
  } catch (error) {
    console.warn('저장된 merge 다운로드 폴더를 불러오지 못했습니다.', error);
  }
  renderMergeDownloadDirectory();
}

async function chooseMergeDownloadDirectory() {
  if (!supportsMergeDownloadDirectory()) {
    notify('알림', 'Chrome 또는 Edge의 HTTPS/localhost 환경이 필요해요', 'err');
    return null;
  }
  try {
    const handle = await window.showDirectoryPicker({
      id: 'yt-w-merge-download',
      mode: 'readwrite',
      startIn: 'downloads',
    });
    if (!await ensureMergeDownloadDirectoryPermission(handle)) {
      throw new Error('선택한 폴더의 쓰기 권한이 필요합니다');
    }
    await saveMergeDownloadDirectoryHandle(handle, window.indexedDB);
    state.mergeDownloadDirectory = handle;
    renderMergeDownloadDirectory();
    notify('저장됨', `${handle.name} 폴더를 기억했어요`, 'ok');
    return handle;
  } catch (error) {
    if (error?.name === 'AbortError') return null;
    notify('오류', error.message || '폴더를 선택하지 못했습니다', 'err');
    return null;
  }
}

async function executeMerge() {
  if (state.sequence.length < 2) {
    notify('알림', '최소 2개의 파일이 필요해요', 'err'); return;
  }
  const out = currentMergeOutputName();
  const btn = $('btn-execute-merge');
  btn.disabled = true; const orig = btn.textContent; btn.textContent = '작업 등록 중…';
  try {
    const r = await fetch(`${API}/api/merge`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ inputs: state.sequence, output: out, mode: state.mergeMode }),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || '합치기 실패');
    notify('등록됨', `합치기 작업 ${d.id.slice(0,8)}을 시작했어요`, 'ok');
    setDefaultMergeOutputName();
    loadJobs();
  } catch (e) { notify('오류', e.message, 'err'); }
  finally { btn.textContent = orig; renderMergeReady(); }
}

/* ── merge :: jobs ─────────────────────────────────────────────────── */
async function loadJobs() {
  try {
    const r = await fetch(`${API}/api/merge/jobs`);
    const jobs = await r.json();
    state.mergeJobs = jobs;
    renderJobs(jobs);
  } catch (e) {}
}
function renderJobs(jobs) {
  const host = $('merge-jobs');
  if (!jobs.length) {
    host.innerHTML = `<div class="empty">
      <div class="empty-icon">▦</div>
      <div class="empty-title">아직 합치기 작업이 없어요</div>
      <div class="empty-sub">위에서 영상을 골라 합치기를 실행하면 진행 상황이 여기에 표시됩니다</div>
    </div>`;
    return;
  }
  host.innerHTML = `
    <div class="job-row head">
      <div>작업 ID</div>
      <div>저장 파일</div>
      <div>방식</div>
      <div>걸린 시간</div>
      <div></div>
    </div>
    ${jobs.map(j => `
      <div class="job-row">
        <div class="job-id">${j.id.slice(0,8)}</div>
        <div>
          <div class="job-out">${escapeHtml(j.output)}</div>
          <div class="job-msg ${j.status === 'failed' ? 'failed' : ''}">${j.inputs.length}개 클립 · ${escapeHtml((j.message || '').slice(0,80))}</div>
          ${j.status === 'running' ? '<div class="job-progress indeterminate"><div></div></div>' : ''}
        </div>
        <div class="job-mode">${j.mode === 'concat' ? '빠르게' : '재인코딩'}</div>
        <div class="job-elapsed">${fmtDuration(j.elapsed_seconds)}</div>
        <div class="actions">
          ${jobStateChip(j.status)}
          ${j.status === 'done' && supportsMergeDownloadDirectory()
            ? `<button class="btn sm" type="button" onclick="saveMergedJob('${j.id}')" ${state.savingMergeJobs.has(j.id) ? 'disabled' : ''}>${state.savingMergeJobs.has(j.id) ? '저장 중…' : '내 폴더에 저장'}</button>`
            : ''}
          ${j.status === 'done' ? `<a class="btn sm ghost" href="${API}/api/merge/jobs/${j.id}/download">그냥 받기</a>` : ''}
          ${(j.status === 'queued' || j.status === 'running') ? `<button class="btn sm danger" onclick="cancelJob('${j.id}')">취소</button>` : ''}
        </div>
      </div>
    `).join('')}
  `;
}
async function saveMergedJob(jobId) {
  const job = state.mergeJobs.find(item => item.id === jobId);
  if (!job || state.savingMergeJobs.has(jobId)) return;

  state.savingMergeJobs.add(jobId);
  renderJobs(state.mergeJobs);
  try {
    let directoryHandle = state.mergeDownloadDirectory;
    if (!directoryHandle) directoryHandle = await chooseMergeDownloadDirectory();
    if (!directoryHandle) return;
    if (!await ensureMergeDownloadDirectoryPermission(directoryHandle)) {
      throw new Error('선택한 폴더의 쓰기 권한이 필요합니다');
    }
    const savedFileName = await writeMergedFileToDirectory(
      `${API}/api/merge/jobs/${jobId}/download`,
      job.output,
      directoryHandle,
    );
    notify('저장 완료', `${savedFileName} 파일을 저장했어요`, 'ok');
  } catch (error) {
    notify('오류', error.message || '병합 파일을 저장하지 못했습니다', 'err');
  } finally {
    state.savingMergeJobs.delete(jobId);
    renderJobs(state.mergeJobs);
  }
}
async function cancelJob(id) {
  try {
    const r = await fetch(`${API}/api/merge/jobs/${id}/cancel`, { method: 'POST' });
    if (!r.ok) { const e = await r.json(); throw new Error(e.detail); }
    notify('완료', `작업 ${id.slice(0,8)}을 취소했어요`, 'ok');
    loadJobs();
  } catch (e) { notify('오류', e.message, 'err'); }
}

/* ── split ─────────────────────────────────────────────────────────── */
function renderSplitFileList() {
  const host = $('split-file-list');
  if (!host) return;
  const filteredFiles = filterSplitFiles(state.files, state.splitSearchQuery);
  $('split-file-count').textContent = state.splitSearchQuery
    ? `${filteredFiles.length}/${state.files.length}개`
    : `${state.files.length}개`;
  if (!state.files.length) {
    host.innerHTML = `<div class="empty">
      <div class="empty-icon">⌘</div>
      <div class="empty-title">나눌 영상이 없어요</div>
      <div class="empty-sub">다운로드하거나 합친 영상이 여기에 표시됩니다. PC에 있는 영상은 위의 'PC 영상 올리기'로 가져올 수 있어요.</div>
      <button class="btn primary" type="button" onclick="chooseSplitUpload()">PC 영상 올리기</button>
    </div>`;
    return;
  }
  if (!filteredFiles.length) {
    host.innerHTML = `<div class="empty">
      <div class="empty-icon">⌕</div>
      <div class="empty-title">검색 결과가 없어요</div>
      <div class="empty-sub">다른 파일명이나 경로로 검색해 주세요</div>
    </div>`;
    return;
  }
  state.splitGroups = buildFileGroups(filteredFiles);
  host.innerHTML = state.splitGroups.map((group, groupIdx) => {
    const open = state.splitGroupOpen.has(group.id) || Boolean(state.splitSearchQuery);
    const selected = group.paths.includes(state.splitSelectedPath);
    const partBadge = group.partLabel
      ? `<span class="part-chip">${escapeHtml(group.partLabel)}</span>`
      : '';
    return `
      <div class="file-group ${open ? 'open' : ''} ${selected ? 'selected' : ''}">
        <div class="file-group-head split-file-group-head"
             onclick="toggleSplitGroup(${groupIdx})">
          <span class="tree-toggle" aria-hidden="true">▸</span>
          <div class="file-group-title" title="${escapeHtml(group.name)}">${escapeHtml(group.name)}</div>
          ${partBadge}
          <div class="file-meta nowrap">${group.paths.length}개</div>
        </div>
        <div class="file-group-children">
          ${group.files.map(file => renderSplitFileRow(file)).join('')}
        </div>
      </div>`;
  }).join('');
}

function renderSplitFileRow(file) {
  const selected = file.path === state.splitSelectedPath;
  const safePath = escapeHtml(file.path).replace(/'/g, "\\'");
  return `
    <label class="file-row child split-file-row ${selected ? 'selected' : ''}">
      <span class="selection-control selection-radio">
        <input type="radio" name="split-source" aria-label="${escapeHtml(file.name)} 선택"
               ${selected ? 'checked' : ''} onchange="selectSplitFile('${safePath}')" />
        <span class="selection-mark" aria-hidden="true"></span>
      </span>
      <div class="file-name" title="${escapeHtml(file.path)}">${escapeHtml(file.name)}</div>
      <div class="file-meta nowrap">${fmtBytes(file.size_bytes)}</div>
      <div class="file-meta nowrap">${fmtAge(file.mtime)}</div>
    </label>`;
}

function toggleSplitGroup(groupIdx) {
  const group = state.splitGroups[groupIdx];
  if (!group) return;
  if (state.splitGroupOpen.has(group.id)) state.splitGroupOpen.delete(group.id);
  else state.splitGroupOpen.add(group.id);
  renderSplitFileList();
}

function filterSplitFiles(files, query) {
  const normalizedQuery = (query || '').trim().toLowerCase();
  if (!normalizedQuery) return files;
  return files.filter(file =>
    `${file.name || ''}\n${file.path || ''}`.toLowerCase().includes(normalizedQuery));
}

function setSplitSearch(query) {
  state.splitSearchQuery = query || '';
  renderSplitFileList();
}

function chooseSplitUpload() {
  $('split-upload-input').click();
}

function setSplitUploadProgress(percent, message) {
  const host = $('split-upload-status');
  if (!host) return;
  if (percent == null) {
    host.style.display = 'none';
    return;
  }
  host.style.display = '';
  $('split-upload-progress').style.width = `${Math.max(0, Math.min(100, percent))}%`;
  $('split-upload-text').textContent = message;
}

function requestSplitUpload(file, onProgress) {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open('POST', `${API}/api/split/upload?filename=${encodeURIComponent(file.name)}`);
    request.setRequestHeader('Content-Type', file.type || 'application/octet-stream');
    request.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(Math.round(event.loaded / event.total * 100));
    };
    request.onerror = () => reject(new Error('영상 업로드 중 네트워크 오류가 발생했습니다'));
    request.onload = () => {
      let data = {};
      try { data = JSON.parse(request.responseText || '{}'); } catch (error) {}
      if (request.status >= 200 && request.status < 300) resolve(data);
      else reject(new Error(data.detail || '영상 업로드에 실패했습니다'));
    };
    request.send(file);
  });
}

async function uploadSplitVideo(file) {
  if (!file) return;
  const button = $('btn-split-upload');
  const originalText = button.textContent;
  button.disabled = true;
  button.textContent = '업로드 중…';
  setSplitUploadProgress(0, `${file.name} · 0%`);
  try {
    const uploaded = await requestSplitUpload(
      file,
      percent => setSplitUploadProgress(percent, `${file.name} · ${percent}%`),
    );
    state.splitSearchQuery = '';
    $('split-file-search').value = '';
    await loadFiles(true);
    selectSplitFile(uploaded.path);
    setSplitUploadProgress(100, `${uploaded.name} · 업로드 완료`);
    notify('업로드 완료', `${uploaded.name} 영상을 선택했어요`, 'ok');
    setTimeout(() => setSplitUploadProgress(null, ''), 1800);
  } catch (error) {
    setSplitUploadProgress(0, error.message || '업로드 실패');
    notify('오류', error.message || '영상 업로드 실패', 'err');
  } finally {
    button.disabled = false;
    button.textContent = originalText;
  }
}

function selectSplitFile(path) {
  state.splitSelectedPath = path;
  const group = buildFileGroups(state.files).find(item => item.paths.includes(path));
  if (group) state.splitGroupOpen.add(group.id);
  renderSplitFileList();
  renderSplitSelection();
}

function setSplitStrategy(strategy) {
  state.splitStrategy = strategy === 'parts' ? 'parts' : 'interval';
  $('split-mode-interval').classList.toggle('active', state.splitStrategy === 'interval');
  $('split-mode-parts').classList.toggle('active', state.splitStrategy === 'parts');
  $('split-interval-fields').style.display = state.splitStrategy === 'interval' ? '' : 'none';
  $('split-parts-fields').style.display = state.splitStrategy === 'parts' ? '' : 'none';
  renderSplitSelection();
}

function setSplitParts(parts) {
  $('split-parts').value = parts;
  renderSplitSelection();
}

function splitOutputNames(path, count = 2) {
  const name = mergeFileName(path || '원본명.ext');
  const dotIndex = name.lastIndexOf('.');
  const stem = dotIndex > 0 ? name.slice(0, dotIndex) : name;
  const extension = dotIndex > 0 ? name.slice(dotIndex) : '';
  return Array.from({ length: count }, (_, index) => `${stem}-${index + 1}${extension}`);
}

function renderSplitSelection() {
  const selectedHost = $('split-selected-file');
  const previewHost = $('split-output-preview');
  if (!selectedHost || !previewHost) return;
  selectedHost.textContent = state.splitSelectedPath || '왼쪽 목록에서 영상 하나를 골라 주세요';
  const requestedParts = Math.max(2, Number.parseInt($('split-parts')?.value || '2', 10) || 2);
  const previewCount = state.splitStrategy === 'parts' ? Math.min(requestedParts, 3) : 2;
  const names = splitOutputNames(state.splitSelectedPath, previewCount);
  const suffix = state.splitStrategy === 'parts' && requestedParts <= 3 ? '' : ', …';
  previewHost.textContent = `저장 이름: split/${names.join(', split/')}${suffix}`;
  renderSplitReady();
}

function renderSplitReady() {
  const bar = $('split-ready');
  const text = $('split-ready-text');
  const button = $('btn-execute-split');
  const stepNo = $('split-step-no');
  if (!bar || !text || !button) return;

  let blockedReason = '';
  if (!state.splitSelectedPath) {
    blockedReason = '왼쪽 목록에서 나눌 영상을 하나 골라 주세요.';
  } else if (state.splitStrategy === 'interval') {
    const intervalHours = Number($('split-interval-hours')?.value);
    if (!Number.isFinite(intervalHours) || intervalHours <= 0) {
      blockedReason = '나누는 간격은 0보다 큰 시간이어야 합니다.';
    }
  } else {
    const parts = Number($('split-parts')?.value);
    if (!Number.isInteger(parts) || parts < 2) {
      blockedReason = '등분 수는 2 이상의 정수로 입력해 주세요.';
    }
  }

  button.disabled = Boolean(blockedReason);
  bar.classList.toggle('go', !blockedReason);
  if (stepNo) stepNo.classList.toggle('done', !blockedReason);
  if (blockedReason) {
    text.textContent = blockedReason;
    return;
  }
  /* 파일명은 바로 위 "고른 영상"에 이미 크게 떠 있다. 여기서는 무엇을 어떻게
     자르는지와 원본이 남는지만 말한다. */
  const rule = state.splitStrategy === 'interval'
    ? `${Number($('split-interval-hours').value)}시간 간격으로`
    : `${Number($('split-parts').value)}등분으로`;
  text.textContent = `${rule} 나눠 split 폴더에 저장합니다. 원본은 그대로 남습니다.`;
}

function splitRuleLabel(job) {
  if (job.strategy === 'parts') return `${job.parts}등분`;
  const hours = job.interval_seconds / 3600;
  return `${Number(hours.toFixed(2))}시간 간격`;
}

async function executeSplit() {
  if (!state.splitSelectedPath) {
    notify('알림', '나눌 영상을 선택해 주세요', 'err'); return;
  }

  const payload = { input: state.splitSelectedPath, strategy: state.splitStrategy };
  let ruleText = '';
  if (state.splitStrategy === 'interval') {
    const intervalHours = Number($('split-interval-hours').value);
    if (!Number.isFinite(intervalHours) || intervalHours <= 0) {
      notify('알림', '0보다 큰 시간 간격을 입력해 주세요', 'err'); return;
    }
    payload.interval_seconds = intervalHours * 3600;
    ruleText = `${intervalHours}시간 간격`;
  } else {
    const parts = Number($('split-parts').value);
    if (!Number.isInteger(parts) || parts < 2) {
      notify('알림', '2 이상의 정수로 등분 수를 입력해 주세요', 'err'); return;
    }
    payload.parts = parts;
    ruleText = `${parts}등분`;
  }

  const sourceName = mergeFileName(state.splitSelectedPath);
  if (!confirm(`${sourceName} 영상을 ${ruleText}으로 나눌까요?\n원본은 유지되고 split 폴더에 번호를 붙여 저장합니다.`)) return;

  const button = $('btn-execute-split');
  const originalText = button.textContent;
  button.disabled = true;
  button.textContent = '작업 등록 중…';
  try {
    const response = await fetch(`${API}/api/split`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || '영상 나누기 실패');
    notify('등록됨', `${data.total_parts}개 파일로 나누는 작업을 시작했어요`, 'ok');
    loadSplitJobs();
  } catch (error) {
    notify('오류', error.message || '영상 나누기 실패', 'err');
  } finally {
    button.textContent = originalText;
    renderSplitReady();
  }
}

async function loadSplitJobs() {
  try {
    const response = await fetch(`${API}/api/split/jobs`);
    const jobs = await response.json();
    state.splitJobs = jobs;
    renderSplitJobs(jobs);
  } catch (error) {}
}

function renderSplitJobs(jobs) {
  const host = $('split-jobs');
  if (!host) return;
  if (!jobs.length) {
    host.innerHTML = `<div class="empty">
      <div class="empty-icon">✂</div>
      <div class="empty-title">아직 나누기 작업이 없어요</div>
      <div class="empty-sub">위에서 영상과 나누는 기준을 골라 실행하면 진행 상황이 여기에 표시됩니다</div>
    </div>`;
    return;
  }
  host.innerHTML = `
    <div class="job-row head split-job-row">
      <div>작업 ID</div><div>원본 / 저장 파일</div><div>기준</div><div>진행</div><div></div>
    </div>
    ${jobs.map(job => {
      const downloadList = job.status === 'done'
        ? `<details class="split-downloads"><summary>${job.outputs.length}개 파일 받기</summary>
            <div>${job.outputs.map((output, index) => `<a href="${API}/api/split/jobs/${job.id}/download/${index + 1}">↓ ${escapeHtml(mergeFileName(output))}</a>`).join('')}</div>
           </details>`
        : '';
      /* 나누기는 남은 조각 수를 아니까 실제 비율로 그린다. */
      const donePercent = job.total_parts > 0
        ? Math.round(job.completed_parts / job.total_parts * 100)
        : 0;
      const progress = job.status === 'running'
        ? `<div class="job-progress"><div style="width:${donePercent}%"></div></div>`
        : '';
      return `
        <div class="job-row split-job-row">
          <div class="job-id">${job.id.slice(0,8)}</div>
          <div>
            <div class="job-out">${escapeHtml(job.input)}</div>
            <div class="job-msg ${job.status === 'failed' ? 'failed' : ''}">${escapeHtml((job.message || '').slice(0,100))}</div>
            ${progress}
            ${downloadList}
          </div>
          <div class="job-mode">${splitRuleLabel(job)}</div>
          <div class="job-elapsed">${job.completed_parts}/${job.total_parts}개<br/>${fmtDuration(job.elapsed_seconds)}</div>
          <div class="actions">${jobStateChip(job.status)}
            ${(job.status === 'queued' || job.status === 'running') ? `<button class="btn sm danger" onclick="cancelSplitJob('${job.id}')">취소</button>` : ''}
          </div>
        </div>`;
    }).join('')}`;
}

async function cancelSplitJob(jobId) {
  try {
    const response = await fetch(`${API}/api/split/jobs/${jobId}/cancel`, { method: 'POST' });
    if (!response.ok) { const error = await response.json(); throw new Error(error.detail); }
    notify('완료', `작업 ${jobId.slice(0,8)}을 취소했어요`, 'ok');
    loadSplitJobs();
  } catch (error) {
    notify('오류', error.message, 'err');
  }
}

/* ── YouTube upload ──────────────────────────────────────────── */
function filterYouTubeUploadFiles(files) {
  const allowedDirectories = new Set(['merged', 'split', 'uploads', 'web_downloads']);
  const videoExtensions = new Set([
    'avi', 'm4v', 'mkv', 'mov', 'mp4', 'mpeg', 'mpg', 'ts', 'webm',
  ]);
  return (files || []).filter(file => {
    const path = String(file?.path || '');
    if (!path || path.includes('\\')) return false;
    const pathParts = path.split('/');
    if (pathParts.some(part => !part || part === '.' || part === '..' || part.startsWith('.'))) return false;
    if (pathParts.length < 2 || !allowedDirectories.has(pathParts[0])) return false;
    const extensionMatch = pathParts[pathParts.length - 1].match(/\.([^.]+)$/);
    return Boolean(extensionMatch && videoExtensions.has(extensionMatch[1].toLowerCase()));
  });
}

function renderYouTubeUploadFileList() {
  const host = $('youtube-upload-file-list');
  if (!host) return;
  const files = filterYouTubeUploadFiles(state.files);
  const allowedPaths = new Set(files.map(file => file.path));
  if (!allowedPaths.has(state.youtubeUploadSelectedPath)) state.youtubeUploadSelectedPath = null;
  $('youtube-upload-file-count').textContent = `${files.length}개`;

  if (!files.length) {
    host.innerHTML = `<div class="empty">
      <div class="empty-icon">⇧</div>
      <div class="empty-title">업로드할 서버 영상이 없어요</div>
      <div class="empty-sub">merged, split, uploads, web_downloads 폴더의 영상 파일만 표시됩니다. PC에서 바로 올리는 기능은 제공하지 않습니다.</div>
    </div>`;
    return;
  }

  host.innerHTML = files.map(file => {
    const selected = file.path === state.youtubeUploadSelectedPath;
    const fileName = file.name || mergeFileName(file.path);
    const topDirectory = String(file.path).split('/')[0];
    const safePathAttribute = escapeHtmlAttribute(file.path);
    const safeNameAttribute = escapeHtmlAttribute(fileName);
    return `<label class="youtube-upload-file-row ${selected ? 'selected' : ''}">
      <span class="selection-control selection-radio">
        <input type="radio" name="youtube-upload-source" value="${safePathAttribute}"
               aria-label="${safeNameAttribute} 선택" ${selected ? 'checked' : ''}
               onchange="selectYouTubeUploadFile(this.value)" />
        <span class="selection-mark" aria-hidden="true"></span>
      </span>
      <div class="youtube-upload-file-main">
        <div class="file-name" title="${safePathAttribute}">${escapeHtml(fileName)}</div>
        <div class="youtube-upload-file-path mono">${escapeHtml(file.path)}</div>
      </div>
      <span class="part-chip">${escapeHtml(topDirectory)}</span>
      <span class="file-meta nowrap">${fmtBytes(file.size_bytes)}</span>
      <span class="file-meta nowrap">${fmtAge(file.mtime)}</span>
    </label>`;
  }).join('');
}

function selectYouTubeUploadFile(path) {
  const allowed = filterYouTubeUploadFiles(state.files).some(file => file.path === path);
  state.youtubeUploadSelectedPath = allowed ? path : null;
  renderYouTubeUploadFileList();
  renderYouTubeUploadReady();
}

function renderYouTubeUploadReady() {
  const button = $('btn-youtube-upload');
  const bar = $('youtube-upload-ready');
  const text = $('youtube-upload-ready-text');
  const selectedSource = $('youtube-upload-selected-source');
  if (!button || !bar || !text || !selectedSource) return;

  const status = state.youtubeOAuthStatus;
  const title = $('youtube-upload-title').value.trim();
  const selected = state.youtubeUploadSelectedPath;
  selectedSource.textContent = selected || '영상을 먼저 골라 주세요.';

  let blockedReason = '';
  if (!status) blockedReason = 'YouTube 계정 상태를 확인하고 있습니다.';
  else if (status.error) blockedReason = status.error;
  else if (!status.configured) blockedReason = '서버에 YouTube OAuth 설정이 필요합니다.';
  else if (!status.connected) blockedReason = 'YouTube 계정을 연결해 주세요.';
  else if (!selected) blockedReason = '업로드할 서버 영상을 골라 주세요.';
  else if (!title) blockedReason = '영상 제목을 입력해 주세요.';

  button.disabled = Boolean(blockedReason);
  bar.classList.toggle('go', !blockedReason);
  $('youtube-upload-step-no')?.classList.toggle('done', !blockedReason);
  text.textContent = blockedReason || `"${title}"을(를) 비공개로 업로드합니다.`;
}

function renderYouTubeOAuthStatus() {
  const chip = $('youtube-oauth-chip');
  const message = $('youtube-oauth-message');
  const connectButton = $('btn-youtube-connect');
  const disconnectButton = $('btn-youtube-disconnect');
  if (!chip || !message || !connectButton || !disconnectButton) return;
  const status = state.youtubeOAuthStatus;

  connectButton.style.display = 'none';
  disconnectButton.style.display = 'none';
  if (!status) {
    chip.className = 'chip dim';
    chip.textContent = '확인 중';
    message.textContent = 'YouTube 계정 연결 상태를 확인하고 있습니다.';
  } else if (status.error) {
    chip.className = 'chip err';
    chip.textContent = '확인 실패';
    message.textContent = status.error;
  } else if (!status.configured) {
    chip.className = 'chip warn';
    chip.textContent = '설정 필요';
    message.textContent = '서버 관리자가 YouTube OAuth client 설정을 완료해야 합니다.';
  } else if (status.connected) {
    chip.className = 'chip ok';
    chip.textContent = '연결됨';
    message.textContent = 'YouTube 계정이 연결되었습니다. 영상을 비공개로 업로드할 수 있습니다.';
    disconnectButton.style.display = '';
  } else {
    chip.className = 'chip amber';
    chip.textContent = '연결 필요';
    message.textContent = 'Google 계정을 연결하면 이 서버의 영상을 YouTube에 올릴 수 있습니다.';
    connectButton.style.display = '';
  }
  renderYouTubeUploadReady();
}

async function loadYouTubeOAuthStatus() {
  state.youtubeOAuthStatus = null;
  renderYouTubeOAuthStatus();
  try {
    const response = await fetch(`${API}/api/youtube/oauth/status`);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || 'YouTube 계정 상태를 확인하지 못했습니다.');
    state.youtubeOAuthStatus = {
      configured: Boolean(data.configured),
      connected: Boolean(data.connected),
    };
  } catch (error) {
    state.youtubeOAuthStatus = {
      configured: false,
      connected: false,
      error: error.message || 'YouTube 계정 상태를 확인하지 못했습니다.',
    };
  }
  renderYouTubeOAuthStatus();
}

async function connectYouTubeAccount() {
  const button = $('btn-youtube-connect');
  button.disabled = true;
  try {
    const response = await fetch(`${API}/api/youtube/oauth/start`, {
      method: 'POST',
      headers: YOUTUBE_MUTATION_HEADERS,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || 'YouTube 계정 연결을 시작하지 못했습니다.');
    if (!data.authorization_url) throw new Error('인증 주소를 받지 못했습니다.');
    const authorizationUrl = new URL(data.authorization_url);
    if (authorizationUrl.protocol !== 'https:') throw new Error('안전한 인증 주소가 아닙니다.');
    window.location.assign(authorizationUrl.href);
  } catch (error) {
    notify('오류', error.message || 'YouTube 계정 연결을 시작하지 못했습니다.', 'err');
    button.disabled = false;
  }
}

async function disconnectYouTubeAccount() {
  if (!confirm('YouTube 계정 연결을 해제할까요?\n진행 중인 업로드에 영향을 줄 수 있습니다.')) return;
  const button = $('btn-youtube-disconnect');
  button.disabled = true;
  try {
    const response = await fetch(`${API}/api/youtube/oauth/connection`, {
      method: 'DELETE',
      headers: YOUTUBE_MUTATION_HEADERS,
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || 'YouTube 계정 연결을 해제하지 못했습니다.');
    }
    notify('연결 해제', 'YouTube 계정 연결을 해제했습니다.', 'ok');
    await loadYouTubeOAuthStatus();
  } catch (error) {
    notify('오류', error.message || 'YouTube 계정 연결을 해제하지 못했습니다.', 'err');
    button.disabled = false;
  }
}

async function submitYouTubeUpload(event) {
  event.preventDefault();
  const title = $('youtube-upload-title').value.trim();
  if (!state.youtubeUploadSelectedPath) {
    notify('알림', '업로드할 서버 영상을 골라 주세요.', 'err'); return;
  }
  if (!title) {
    notify('알림', '영상 제목을 입력해 주세요.', 'err'); return;
  }
  if (!state.youtubeOAuthStatus?.connected) {
    notify('알림', 'YouTube 계정을 먼저 연결해 주세요.', 'err'); return;
  }

  const payload = {
    source: state.youtubeUploadSelectedPath,
    title,
    description: $('youtube-upload-description').value,
    tags: $('youtube-upload-tags').value.split(',').map(tag => tag.trim()).filter(Boolean),
    category_id: $('youtube-upload-category').value,
    made_for_kids: $('youtube-upload-made-for-kids').checked,
  };
  const button = $('btn-youtube-upload');
  button.disabled = true;
  button.textContent = '작업 등록 중…';
  try {
    const response = await fetch(`${API}/api/youtube/uploads`, {
      method: 'POST',
      headers: { ...YOUTUBE_MUTATION_HEADERS, 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || 'YouTube 업로드를 등록하지 못했습니다.');
    const jobLabel = data.id ? ` ${String(data.id).slice(0, 8)}` : '';
    notify('등록됨', `YouTube 업로드 작업${jobLabel}을 등록했습니다.`, 'ok');
    loadYouTubeUploadJobs();
  } catch (error) {
    notify('오류', error.message || 'YouTube 업로드를 등록하지 못했습니다.', 'err');
  } finally {
    button.textContent = '비공개로 업로드';
    renderYouTubeUploadReady();
  }
}

function youtubeUploadProgressPercent(job) {
  const explicitPercent = Number(job.progress_percent);
  if (Number.isFinite(explicitPercent)) return Math.max(0, Math.min(100, explicitPercent));
  const totalBytes = Number(job.total_bytes);
  const uploadedBytes = Number(job.bytes_uploaded);
  if (totalBytes > 0 && Number.isFinite(uploadedBytes)) {
    return Math.max(0, Math.min(100, uploadedBytes / totalBytes * 100));
  }
  return job.status === 'done' ? 100 : 0;
}

function safeYouTubeVideoUrl(videoUrl, videoId) {
  if (videoUrl) {
    try {
      const parsed = new URL(videoUrl);
      const host = parsed.hostname.toLowerCase();
      if (parsed.protocol === 'https:' && (host === 'youtu.be' || host === 'youtube.com' || host.endsWith('.youtube.com'))) {
        return parsed.href;
      }
    } catch (error) {}
  }
  return videoId ? `https://www.youtube.com/watch?v=${encodeURIComponent(videoId)}` : null;
}

async function loadYouTubeUploadJobs() {
  try {
    const response = await fetch(`${API}/api/youtube/uploads`);
    const jobs = await response.json().catch(() => []);
    if (!response.ok) throw new Error('YouTube 업로드 작업을 불러오지 못했습니다.');
    state.youtubeUploadJobs = Array.isArray(jobs) ? jobs : [];
    renderYouTubeUploadJobs(state.youtubeUploadJobs);
  } catch (error) {
    const host = $('youtube-upload-jobs');
    if (host) host.innerHTML = `<div class="empty"><div class="empty-title">작업을 불러오지 못했어요</div><div class="empty-sub">${escapeHtml(error.message)}</div></div>`;
  }
}

function renderYouTubeUploadJobs(jobs) {
  const host = $('youtube-upload-jobs');
  if (!host) return;
  if (!jobs.length) {
    host.innerHTML = `<div class="empty">
      <div class="empty-icon">⇧</div>
      <div class="empty-title">아직 YouTube 업로드 작업이 없어요</div>
      <div class="empty-sub">영상과 정보를 고른 뒤 업로드하면 진행 상황이 여기에 표시됩니다.</div>
    </div>`;
    return;
  }

  host.innerHTML = `<div class="job-row head youtube-upload-job-row">
      <div>작업 ID</div><div>영상 / 진행률</div><div>전송량</div><div>걸린 시간</div><div></div>
    </div>
    ${jobs.map(job => {
      const jobId = String(job.id || '');
      const safeJobId = escapeHtml(jobId).replace(/'/g, "\\'");
      const percent = youtubeUploadProgressPercent(job);
      const roundedPercent = Math.round(percent);
      const videoUrl = job.status === 'done' ? safeYouTubeVideoUrl(job.video_url, job.video_id) : null;
      const active = job.status === 'queued' || job.status === 'running';
      const cancelControl = active && !job.cancel_requested
        ? `<button class="btn sm danger" type="button" onclick="cancelYouTubeUpload('${safeJobId}')">취소</button>`
        : job.cancel_requested ? '<span class="chip warn">취소 요청됨</span>' : '';
      return `<div class="job-row youtube-upload-job-row">
        <div class="job-id">${escapeHtml(jobId.slice(0, 8))}</div>
        <div>
          <div class="job-out">${escapeHtml(job.title || mergeFileName(job.source || ''))}</div>
          <div class="youtube-upload-job-source mono">${escapeHtml(job.source || '')}</div>
          <div class="job-msg ${job.status === 'failed' ? 'failed' : ''}">${escapeHtml((job.message || '').slice(0, 120))}</div>
          <div class="job-progress" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${roundedPercent}">
            <div style="width:${percent}%"></div>
          </div>
        </div>
        <div class="youtube-upload-bytes">${fmtBytes(job.bytes_uploaded)} / ${fmtBytes(job.total_bytes)}<br/><strong>${roundedPercent}%</strong></div>
        <div class="job-elapsed">${fmtDuration(job.elapsed_seconds)}</div>
        <div class="actions">
          ${jobStateChip(job.status)}
          ${cancelControl}
          ${videoUrl ? `<a class="btn sm" href="${escapeHtml(videoUrl)}" target="_blank" rel="noopener noreferrer">YouTube에서 보기</a>` : ''}
        </div>
      </div>`;
    }).join('')}`;
}

async function cancelYouTubeUpload(jobId) {
  try {
    const response = await fetch(`${API}/api/youtube/uploads/${encodeURIComponent(jobId)}/cancel`, {
      method: 'POST',
      headers: YOUTUBE_MUTATION_HEADERS,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || 'YouTube 업로드 취소를 요청하지 못했습니다.');
    notify('취소 요청', `작업 ${jobId.slice(0, 8)}의 취소를 요청했습니다.`, 'ok');
    loadYouTubeUploadJobs();
  } catch (error) {
    notify('오류', error.message || 'YouTube 업로드 취소를 요청하지 못했습니다.', 'err');
  }
}

function handleYouTubeOAuthCallback() {
  const currentUrl = new URL(window.location.href);
  const outcome = currentUrl.searchParams.get('youtube_oauth');
  if (!outcome) return false;
  const messages = {
    connected: ['YouTube 연결 완료', 'YouTube 계정이 연결되었습니다.', 'ok'],
    denied: ['YouTube 연결 취소', 'Google 계정 연결을 허용하지 않았습니다.', 'err'],
    invalid_state: ['YouTube 연결 실패', '연결 요청 상태가 만료되었거나 일치하지 않습니다.', 'err'],
    error: ['YouTube 연결 실패', 'YouTube 계정을 연결하지 못했습니다.', 'err'],
  };
  const callbackMessage = messages[outcome];
  if (!callbackMessage) return false;
  const [title, message, kind] = callbackMessage;
  notify(title, message, kind);
  currentUrl.searchParams.delete('youtube_oauth');
  window.history.replaceState(window.history.state, '', `${currentUrl.pathname}${currentUrl.search}${currentUrl.hash}`);
  state.activeTab = 'youtube-upload';
  return true;
}

/* ── single download ── */
function showDLStep(name) {
  ['analyzing', 'result', 'downloading', 'finished'].forEach(s => {
    $(`dl-step-${s}`).style.display = s === name ? 'block' : 'none';
  });
}
function closeResult() {
  showDLStep(null);
  $('url-input').value = '';
  $('url-input').focus();
}
function setFormat(fmt) {
  state.dlFormat = fmt;
  $('btn-video-fmt').classList.toggle('active', fmt === 'video');
  $('btn-audio-fmt').classList.toggle('active', fmt === 'audio');
  $('quality-container').style.display = fmt === 'video' ? '' : 'none';
}
async function handleAnalyze(e) {
  e.preventDefault();
  const url = $('url-input').value.trim();
  if (!url) return;
  showDLStep('analyzing');
  try {
    const r = await fetch(`${API}/api/video/info`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    });
    if (!r.ok) { const er = await r.json(); throw new Error(er.detail || '영상 정보 가져오기 실패'); }
    const d = await r.json();
    $('video-title').textContent = d.title || 'YouTube Video';
    $('video-author').textContent = `▸ ${d.uploader || 'Unknown'}`;
    $('video-thumb').src = d.thumbnail || '';
    const dur = d.duration || 0;
    const h = Math.floor(dur / 3600), m = Math.floor((dur % 3600) / 60), s = dur % 60;
    $('video-duration').textContent = h > 0
      ? `${h}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`
      : `${m}:${String(s).padStart(2,'0')}`;
    $('video-views').textContent = `${(d.view_count || 0).toLocaleString()} 조회`;
    showDLStep('result');
  } catch (e) {
    notify('오류', e.message || '영상 분석 실패', 'err');
    closeResult();
  }
}
async function startDownload() {
  const url = $('url-input').value.trim();
  const quality = $('quality-select').value;
  showDLStep('downloading');
  try {
    const r = await fetch(`${API}/api/download`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, quality, audio_only: state.dlFormat === 'audio' }),
    });
    if (!r.ok) { const er = await r.json(); throw new Error(er.detail || '다운로드 실패'); }
    const d = await r.json();
    const a = document.createElement('a');
    a.href = `${API}/api/download/file/${d.filename}`;
    a.download = d.filename;
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    $('finish-message').textContent = d.filename;
    showDLStep('finished');
    notify('완료', `${d.filename} 다운로드 완료`, 'ok');
  } catch (e) {
    notify('오류', e.message, 'err');
    closeResult();
  }
}

/* ── notif ─────────────────────────────────────────────────────────── */
let notifTimer = null;
function notify(title, msg, kind = 'info') {
  const n = $('notif');
  n.className = `notif active ${kind}`;
  $('notif-title').textContent = title;
  $('notif-msg').textContent = msg;
  if (notifTimer) clearTimeout(notifTimer);
  notifTimer = setTimeout(() => n.classList.remove('active'), 3500);
}

/* ── boot ──────────────────────────────────────────────────────────── */
systemRefresh();
checkCookie();
loadChannels();
setDefaultMergeOutputName();
restoreMergeDownloadDirectory();
handleYouTubeOAuthCallback();
switchTab(state.activeTab);
setInterval(systemRefresh, 5000);
setInterval(checkCookie, 60000);
setInterval(() => { if (state.activeTab === 'merge') loadJobs(); }, 3000);
setInterval(() => { if (state.activeTab === 'split') loadSplitJobs(); }, 3000);
setInterval(() => { if (state.activeTab === 'youtube-upload') loadYouTubeUploadJobs(); }, 3000);
