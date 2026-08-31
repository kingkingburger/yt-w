
/* ── split ─────────────────────────────────────────────────────────── */
function renderSplitFileList() {
  const host = $('split-file-list');
  if (!host) return;
  const filteredFiles = filterSplitFiles(state.files, state.splitSearchQuery);
  $('split-file-count').textContent = state.splitSearchQuery
    ? `${filteredFiles.length}/${state.files.length}개`
    : `${state.files.length}개`;
  if (!state.files.length) {
    host.innerHTML = emptyState({
      icon: '⌘',
      title: '나눌 영상이 없어요',
      sub: `다운로드하거나 합친 영상이 여기에 표시됩니다. PC에 있는 영상은 위의 'PC 영상 올리기'로 가져올 수 있어요.`,
      action: '<button class="btn primary" type="button" onclick="chooseSplitUpload()">PC 영상 올리기</button>',
    });
    return;
  }
  if (!filteredFiles.length) {
    host.innerHTML = emptyState({
      icon: '⌕',
      title: '검색 결과가 없어요',
      sub: '다른 파일명이나 경로로 검색해 주세요',
    });
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
    host.innerHTML = emptyState({
      icon: '✂',
      title: '아직 나누기 작업이 없어요',
      sub: '위에서 영상과 나누는 기준을 골라 실행하면 진행 상황이 여기에 표시됩니다',
    });
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
    await throwIfResponseFailed(response);
    notify('완료', `작업 ${jobId.slice(0,8)}을 취소했어요`, 'ok');
    loadSplitJobs();
  } catch (error) {
    notify('오류', error.message, 'err');
  }
}
