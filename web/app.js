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
  dlFormat: 'video',
  bootTime: null,
};

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
const initial = (name) => {
  const c = (name || '').trim().charAt(0);
  return c ? c.toUpperCase() : '·';
};

/* ── tabs ──────────────────────────────────────────────────────────── */
function switchTab(tab) {
  state.activeTab = tab;
  document.querySelectorAll('.nav-btn').forEach(b =>
    b.classList.toggle('active', b.dataset.tab === tab));
  document.querySelectorAll('.panel').forEach(p =>
    p.classList.toggle('active', p.id === `panel-${tab}`));
  if (tab === 'merge') { loadFiles(); loadJobs(); }
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
    $('discord-state-text').textContent = s.discord_enabled
      ? '✓  웹후크 URL이 설정되어 있어 라이브/완료/에러 알림이 활성화돼 있습니다'
      : '⚠  DISCORD_WEBHOOK_URL이 비어 있어요. .env에 웹후크 주소를 넣고 컨테이너를 재시작하세요';

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
async function loadFiles() {
  try {
    const r = await fetch(`${API}/api/files`);
    state.files = await r.json();
    const validPaths = new Set(state.files.map(f => f.path));
    state.selectedPaths = new Set(
      [...state.selectedPaths].filter(path => validPaths.has(path))
    );
    state.sequence = state.sequence.filter(path => validPaths.has(path));
    renderFileList();
    renderSequence();
  } catch (e) {}
}
function renderFileList() {
  const host = $('merge-file-list');
  const sourceFiles = availableSourceFiles();
  $('merge-file-count').textContent = `${sourceFiles.length}개 파일`;
  const selectAllBtn = $('btn-select-all');
  if (selectAllBtn) {
    const allSelected = sourceFiles.length > 0
      && sourceFiles.every(f => state.selectedPaths.has(f.path));
    selectAllBtn.textContent = allSelected ? '전체 해제' : '전체 선택';
    selectAllBtn.disabled = sourceFiles.length === 0;
  }
  if (!state.files.length) {
    host.innerHTML = `
      <div class="empty">
        <div class="empty-icon">⌘</div>
        <div class="empty-title">아직 다운로드한 영상이 없어요</div>
        <div class="empty-sub">다운로드 탭이나 라이브 녹화를 통해 영상을 받으면 여기에 표시됩니다</div>
      </div>`;
    return;
  }
  if (!sourceFiles.length) {
    state.sourceGroups = [];
    host.innerHTML = `
      <div class="empty">
        <div class="empty-icon">✓</div>
        <div class="empty-title">추가할 소스 파일이 없어요</div>
        <div class="empty-sub">현재 파일은 모두 merge 목록에 있습니다</div>
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
    const fileWord = group.paths.length === 1 ? 'file' : 'files';
    return `
      <div class="file-group ${open ? 'open' : ''} ${allSelected ? 'selected' : ''}"
           style="--group-color:${group.color}">
        <div class="file-group-head"
             draggable="true"
             ondragstart="sourceGroupDragStart(event, ${groupIdx})"
             ondragend="fileDragEnd(event)"
             onclick="toggleSourceGroup(${groupIdx})">
          <span class="tree-toggle" aria-hidden="true">${open ? 'v' : '>'}</span>
          <input type="checkbox"
                 ${allSelected ? 'checked' : ''}
                 ${someSelected ? 'data-partial="true"' : ''}
                 onclick="event.stopPropagation()"
                 onchange="toggleSourceGroupSelect(${groupIdx}, this.checked)" />
          <div class="file-group-title" title="${escapeHtml(group.name)}">${escapeHtml(group.name)}</div>
          ${partBadge}
          <div class="file-meta nowrap">${group.paths.length} ${fileWord}</div>
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
      <input type="checkbox" ${checked ? 'checked' : ''} onchange="toggleFileSelect('${safePath}', this.checked)" />
      <span class="file-grip" aria-hidden="true">::</span>
      <div class="file-name" title="${escapeHtml(fname)}">${escapeHtml(fname)}</div>
      <div class="file-meta nowrap">${fmtBytes(f.size_bytes)}</div>
      <div class="file-meta nowrap">${fmtAge(f.mtime)}</div>
    </label>`;
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
function toggleSelectAll() {
  const sourceFiles = availableSourceFiles();
  if (!sourceFiles.length) return;
  const allSelected = sourceFiles.every(f => state.selectedPaths.has(f.path));
  if (allSelected) {
    const filePaths = new Set(sourceFiles.map(f => f.path));
    filePaths.forEach(p => state.selectedPaths.delete(p));
    state.sequence = state.sequence.filter(p => !filePaths.has(p));
  } else {
    buildFileGroups(sourceFiles).flatMap(group => group.paths).forEach(path => {
      if (!state.selectedPaths.has(path)) {
        state.selectedPaths.add(path);
        if (!state.sequence.includes(path)) state.sequence.push(path);
      }
    });
  }
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
const GROUP_COLORS = [
  '#e6a04d',
  '#6fb7ff',
  '#7ccc92',
  '#d78bff',
  '#ff8f8f',
  '#6ed6c5',
  '#f0d36c',
  '#9aa8ff',
];
function colorForGroup(key) {
  let hash = 0;
  for (let i = 0; i < key.length; i += 1) {
    hash = ((hash << 5) - hash + key.charCodeAt(i)) | 0;
  }
  return GROUP_COLORS[Math.abs(hash) % GROUP_COLORS.length];
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
  const group = infos[0]?.group || '';
  return group ? `${group} - part ${first}-${last}` : `part ${first}-${last}`;
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
        name: info?.group || mergeFileName(file.path),
        isPartGroup: Boolean(info),
        files: [],
        paths: [],
        color: colorForGroup(id),
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
  return `${first.group} - part ${firstNum}-${lastNum}${first.suffix}`;
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
  $('merge-seq-count').textContent = state.sequenceViewMode === 'compact'
    ? `${state.sequence.length}개 클립 · ${rows.length}줄`
    : `${state.sequence.length}개 클립`;
  const compactBtn = $('seq-view-compact');
  const fullBtn = $('seq-view-full');
  if (compactBtn) compactBtn.classList.toggle('active', state.sequenceViewMode === 'compact');
  if (fullBtn) fullBtn.classList.toggle('active', state.sequenceViewMode === 'full');
  const sortBtn = $('btn-sort-sequence-name');
  if (sortBtn) sortBtn.disabled = state.sequence.length < 2;
  if (!state.sequence.length) {
    host.classList.add('empty-seq');
    host.classList.remove('compact', 'full');
    host.innerHTML = '← 왼쪽에서 파일을 선택해 주세요';
    return;
  }
  host.classList.remove('empty-seq');
  host.classList.toggle('compact', state.sequenceViewMode === 'compact');
  host.classList.toggle('full', state.sequenceViewMode === 'full');
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
    const rowInfo = getPartInfo(row.paths[0]);
    const rowColor = colorForGroup(rowInfo?.key || row.paths[0]);
    return `
      <div class="seq-item ${blockSize > 1 ? 'part-block' : ''}" draggable="true" data-idx="${row.start}"
           style="--group-color:${rowColor}"
           ondragstart="seqDragStart(event, ${row.start})"
           ondragover="seqDragOver(event, ${row.start})"
           ondragleave="seqDragLeave(event, ${row.start})"
           ondrop="seqDrop(event, ${row.start})"
           ondragend="seqDragEnd(event)">
        <div class="grip">⋮⋮</div>
        <div class="idx">${idxLabel}</div>
        <div class="name" title="${escapeHtml(title)}">${escapeHtml(fname)}</div>
        ${blockBadge}
        <button class="btn sm danger" onclick="${removeAction}">✕</button>
      </div>`;
  }).join('');
}
function clearSequence() {
  state.sequence = []; state.selectedPaths.clear();
  refreshDefaultMergeOutputName();
  renderFileList(); renderSequence();
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
}
async function executeMerge() {
  if (state.sequence.length < 2) {
    notify('알림', '최소 2개의 파일이 필요해요', 'err'); return;
  }
  const out = currentMergeOutputName();
  const btn = $('btn-execute-merge');
  btn.disabled = true; const orig = btn.textContent; btn.textContent = '◴ 작업 등록 중…';
  try {
    const r = await fetch(`${API}/api/merge`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ inputs: state.sequence, output: out, mode: state.mergeMode }),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || '합치기 실패');
    notify('완료', `합치기 작업 ${d.id.slice(0,8)} 등록`, 'ok');
    setDefaultMergeOutputName();
    loadJobs();
  } catch (e) { notify('오류', e.message, 'err'); }
  finally { btn.disabled = false; btn.textContent = orig; }
}

/* ── merge :: jobs ─────────────────────────────────────────────────── */
async function loadJobs() {
  try {
    const r = await fetch(`${API}/api/merge/jobs`);
    const jobs = await r.json();
    renderJobs(jobs);
  } catch (e) {}
}
function renderJobs(jobs) {
  const host = $('merge-jobs');
  if (!jobs.length) {
    host.innerHTML = `<div class="empty">
      <div class="empty-icon">▦</div>
      <div class="empty-title">아직 합치기 작업이 없어요</div>
      <div class="empty-sub">위에서 파일을 골라 합치기를 실행하면 여기에 표시됩니다</div>
    </div>`;
    return;
  }
  const stateChip = (st) => {
    const map = {
      queued:    ['대기',   'dim'],
      running:   ['진행 중', 'amber'],
      done:      ['완료',   'ok'],
      failed:    ['실패',   'err'],
      cancelled: ['취소됨', 'warn'],
    };
    const [t, c] = map[st] || [st, 'dim'];
    return `<span class="chip ${c}">${t}</span>`;
  };
  host.innerHTML = `
    <div class="job-row head">
      <div>작업 ID</div>
      <div>출력 파일</div>
      <div>방식</div>
      <div>경과</div>
      <div></div>
    </div>
    ${jobs.map(j => `
      <div class="job-row">
        <div class="job-id">${j.id.slice(0,8)}</div>
        <div>
          <div style="color: var(--fg); font-weight:500;">${escapeHtml(j.output)}</div>
          <div style="color:var(--fg-mute); font-size:11px; margin-top:2px;">
            ${j.inputs.length}개 클립 · ${escapeHtml((j.message || '').slice(0,80))}
          </div>
        </div>
        <div class="job-mode">${j.mode === 'concat' ? '빠르게' : '재인코딩'}</div>
        <div class="mono" style="color: var(--fg-dim); font-size:12px;">${fmtDuration(j.elapsed_seconds)}</div>
        <div class="actions" style="text-align:right">
          ${stateChip(j.status)}
          ${j.status === 'done' ? `<a class="btn sm" href="${API}/api/merge/jobs/${j.id}/download">↓ 받기</a>` : ''}
          ${(j.status === 'queued' || j.status === 'running') ? `<button class="btn sm danger" onclick="cancelJob('${j.id}')">취소</button>` : ''}
        </div>
      </div>
    `).join('')}
  `;
}
async function cancelJob(id) {
  try {
    const r = await fetch(`${API}/api/merge/jobs/${id}/cancel`, { method: 'POST' });
    if (!r.ok) { const e = await r.json(); throw new Error(e.detail); }
    notify('완료', `작업 ${id.slice(0,8)}을 취소했어요`, 'ok');
    loadJobs();
  } catch (e) { notify('오류', e.message, 'err'); }
}

/* ── single download ───────────────────────────────────────────────── */
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
switchTab(state.activeTab);
setInterval(systemRefresh, 5000);
setInterval(checkCookie, 60000);
setInterval(() => { if (state.activeTab === 'merge') loadJobs(); }, 3000);
