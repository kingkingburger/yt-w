
/* ── monitor / channels ────────────────────────────────────────────── */
async function loadChannels() {
  try {
    const r = await fetch(`${API}/api/channels`);
    const channels = await r.json();
    renderChannelList(channels);
  } catch (e) {}
}

/* 채널 목록은 라이브 녹화 탭 한 곳에서만 관리한다. 같은 목록을 두 탭에
   나눠 두면 어느 쪽에서 껐는지 사용자가 외워야 한다. */
function renderChannelList(channels) {
  const host = $('channel-list');
  if (!host) return;
  if (!channels.length) {
    host.innerHTML = emptyState({
      icon: '+',
      title: '감시할 채널이 없어요',
      sub: '유튜브 채널을 등록하면 라이브가 시작될 때 자동으로 녹화해요',
      action: '<button class="btn primary" onclick="openAddChannelModal()">+ 첫 채널 추가하기</button>',
    });
    return;
  }
  host.innerHTML = `
    <div class="channel-list">
      ${channels.map((c) => renderChannelRow(c)).join('')}
    </div>`;
}

function renderChannelRow(channel) {
  const name = escapeHtml(channel.name);
  const idAttr = escapeHtmlAttribute(channel.id);
  const confirming = state.pendingChannelDelete === channel.id;
  return `
    <div class="channel-row${confirming ? ' confirming' : ''}">
      <div class="channel-avatar">${escapeHtml(initial(channel.name))}</div>
      <div class="channel-info">
        <div class="channel-name">${name}</div>
        <div class="channel-url">${escapeHtml(channel.url)}</div>
      </div>
      <span class="chip ${channel.enabled ? 'ok' : 'dim'}">${channel.enabled ? '감시 중' : '일시중지'}</span>
      <div class="actions">
        <button class="btn sm" onclick="toggleChannel('${idAttr}', ${!channel.enabled})">${channel.enabled ? '일시중지' : '감시 시작'}</button>
        <button class="btn sm danger" onclick="askDeleteChannel('${idAttr}')"
                aria-expanded="${confirming}">삭제</button>
      </div>
    </div>
    ${confirming ? renderDeleteConfirm(idAttr, name) : ''}`;
}

/* 지우기 전에 무엇이 사라지고 무엇이 남는지 같은 자리에서 말한다.
   모달 대신 행을 펼치는 쪽이 목록의 맥락을 잃지 않는다. */
function renderDeleteConfirm(idAttr, nameHtml) {
  return `
    <div class="channel-confirm" role="alert">
      <svg class="channel-confirm-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"
           stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M10.3 3.9L1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" />
        <line x1="12" y1="9" x2="12" y2="13" />
        <line x1="12" y1="17" x2="12.01" y2="17" />
      </svg>
      <div class="channel-confirm-text">
        <b>${nameHtml}</b>을(를) 감시 목록에서 지웁니다. 이미 받아둔 영상 파일은 그대로 남습니다.
      </div>
      <div class="actions">
        <button class="btn sm" onclick="cancelDeleteChannel()">취소</button>
        <button class="btn sm danger-solid" onclick="deleteChannel('${idAttr}')">지우기</button>
      </div>
    </div>`;
}

function askDeleteChannel(id) {
  state.pendingChannelDelete = state.pendingChannelDelete === id ? null : id;
  loadChannels();
}

function cancelDeleteChannel() {
  state.pendingChannelDelete = null;
  loadChannels();
}

/* ── 최근 녹화 ─────────────────────────────────────────────────────── */
const RECENT_RECORDING_LIMIT = 8;
const RECORDING_DIRECTORY_NAMES = ['live', 'merged'];

async function loadRecentRecordings(refresh = false) {
  const host = $('recent-recordings');
  if (!host) return;
  try {
    const r = await fetch(`${API}/api/files${refresh ? '?refresh=true' : ''}`);
    const files = await r.json();
    // 녹화 산출물은 live(원본)와 merged(자동 병합)에 쌓인다. 웹에서 받은 파일과 섞지 않는다.
    state.recentRecordings = files
      .filter(f => RECORDING_DIRECTORY_NAMES.includes(String(f.path).split('/')[0]))
      .slice(0, RECENT_RECORDING_LIMIT);
    renderRecentRecordings();
  } catch (e) {}
}

function renderRecentRecordings() {
  const host = $('recent-recordings');
  if (!host) return;
  const files = state.recentRecordings;
  const countEl = $('recording-count');
  if (countEl) countEl.textContent = `${files.length}개`;
  if (!files.length) {
    host.innerHTML = emptyState({
      icon: '●',
      title: '아직 녹화된 영상이 없어요',
      sub: '감시 중인 채널이 라이브를 시작하면 녹화한 영상이 여기에 쌓입니다',
    });
    return;
  }
  host.innerHTML = `<div class="recent-list">${files.map(f => `
    <div class="recent-row">
      <div class="recent-mark ok" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"
             stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12" /></svg>
      </div>
      <div class="recent-info">
        <div class="recent-name">${escapeHtml(f.name)}</div>
        <div class="recent-meta">${fmtBytes(f.size_bytes)} · ${fmtAge(f.mtime)} · ${escapeHtml(String(f.path).split('/')[0])}</div>
      </div>
      <div class="actions">
        <button class="btn sm" onclick="switchTab('split')">나누기로</button>
      </div>
    </div>`).join('')}</div>`;
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
    await throwIfResponseFailed(r);
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
    await throwIfResponseFailed(r);
    notify('완료', `채널을 ${enabled ? '활성화' : '비활성화'}했어요`, 'ok');
    loadChannels(); systemRefresh();
  } catch (e) { notify('오류', e.message, 'err'); }
}
async function deleteChannel(id) {
  state.pendingChannelDelete = null;
  try {
    const r = await fetch(`${API}/api/channels/${id}`, { method: 'DELETE' });
    await throwIfResponseFailed(r);
    notify('완료', '채널을 삭제했어요', 'ok');
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
