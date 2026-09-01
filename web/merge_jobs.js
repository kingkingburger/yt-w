
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
    path.classList.remove('mono');
    note.textContent = 'Chrome 또는 Edge의 HTTPS/localhost 환경에서 사용할 수 있습니다.';
    button.disabled = true;
    return;
  }

  const handle = state.mergeDownloadDirectory;
  path.textContent = handle ? handle.name : '선택되지 않음';
  path.classList.toggle('mono', Boolean(handle));
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
    host.innerHTML = emptyState({
      icon: '▦',
      title: '아직 합치기 작업이 없어요',
      sub: '위에서 영상을 골라 합치기를 실행하면 진행 상황이 여기에 표시됩니다',
    });
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
    await throwIfResponseFailed(r);
    notify('완료', `작업 ${id.slice(0,8)}을 취소했어요`, 'ok');
    loadJobs();
  } catch (e) { notify('오류', e.message, 'err'); }
}
