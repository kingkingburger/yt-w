
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
    host.innerHTML = emptyState({
      icon: '+',
      title: '아직 등록된 채널이 없어요',
      sub: '유튜브 채널을 추가하면 라이브 시작 시 자동으로 녹화돼요',
      action: '<button class="btn primary" onclick="openAddChannelModal()">+ 첫 채널 추가하기</button>',
    });
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
    host.innerHTML = emptyState({
      icon: '+',
      title: '감시할 채널이 없어요',
      sub: '먼저 유튜브 채널을 등록해야 자동 녹화를 시작할 수 있어요',
      action: '<button class="btn primary" onclick="openAddChannelModal()">+ 채널 추가하기</button>',
    });
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
async function deleteChannel(id, name) {
  if (!confirm(`'${name}' 채널을 삭제할까요?`)) return;
  try {
    const r = await fetch(`${API}/api/channels/${id}`, { method: 'DELETE' });
    await throwIfResponseFailed(r);
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
