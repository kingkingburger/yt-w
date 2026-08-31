
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
