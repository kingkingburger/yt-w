
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
    loadRecentFiles(true);
  } catch (e) {
    notify('오류', e.message, 'err');
    closeResult();
  }
}

/* ── 최근 받은 영상 ────────────────────────────────────────────────── */
/* 받은 결과가 화면에 남지 않으면 확인하려고 탐색기를 열게 된다. */
const RECENT_FILE_LIMIT = 8;
const DOWNLOAD_DIRECTORY_NAME = 'web_downloads';

async function loadRecentFiles(refresh = false) {
  const host = $('recent-files');
  if (!host) return;
  try {
    const r = await fetch(`${API}/api/files${refresh ? '?refresh=true' : ''}`);
    await throwIfResponseFailed(r, '최근 받은 영상을 불러오지 못했습니다');
    const files = await r.json();
    state.recentFiles = files
      .filter(f => String(f.path).split('/')[0] === DOWNLOAD_DIRECTORY_NAME)
      .slice(0, RECENT_FILE_LIMIT);
    renderRecentFiles();
  } catch (error) {
    renderLoadFailure('recent-files', '최근 받은 영상을 불러오지 못했어요', error);
  }
}

function renderRecentFiles() {
  const host = $('recent-files');
  if (!host) return;
  const files = state.recentFiles;
  const countEl = $('recent-file-count');
  if (countEl) countEl.textContent = `${files.length}개`;
  if (!files.length) {
    host.innerHTML = emptyState({
      icon: '↓',
      title: '아직 받아둔 영상이 없어요',
      sub: '위에 유튜브 주소를 붙여넣으면 받은 영상이 여기에 쌓입니다',
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
        <div class="recent-meta">${fmtBytes(f.size_bytes)} · ${fmtAge(f.mtime)}</div>
      </div>
      <div class="actions">
        <button class="btn sm" onclick="switchTab('merge')">합치기로</button>
        <button class="btn sm" onclick="switchTab('split')">나누기로</button>
      </div>
    </div>`).join('')}</div>`;
}
