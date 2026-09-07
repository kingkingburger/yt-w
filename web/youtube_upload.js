
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

/* 목록 하나가 업로드 대상 고르기와 정리(삭제)를 같이 맡는다. 체크된 파일이 모두
   업로드 대상이다. 하나면 제목 칸의 값을 쓰고, 여러 개면 파일마다 파일명에서 뽑은
   제목으로 작업을 하나씩 등록한다. */
function renderYouTubeUploadFileList() {
  const host = $('youtube-upload-file-list');
  if (!host) return;
  const files = filterYouTubeUploadFiles(state.files);
  const allowedPaths = new Set(files.map(file => file.path));
  state.youtubeUploadSelectedPaths = new Set(
    [...state.youtubeUploadSelectedPaths].filter(path => allowedPaths.has(path))
  );
  const selectedCount = state.youtubeUploadSelectedPaths.size;
  $('youtube-upload-file-count').textContent = selectedCount
    ? `${files.length}개 · ${selectedCount}개 선택`
    : `${files.length}개`;
  const selectAllButton = $('btn-youtube-select-all');
  const deleteSelectedButton = $('btn-youtube-delete-selected');
  if (selectAllButton) {
    selectAllButton.disabled = files.length === 0;
    selectAllButton.textContent = selectedCount === files.length && selectedCount > 0
      ? '전체 해제'
      : '전체 선택';
  }
  if (deleteSelectedButton) deleteSelectedButton.disabled = selectedCount === 0;

  if (!files.length) {
    host.innerHTML = emptyState({
      icon: '⇧',
      title: '업로드할 서버 영상이 없어요',
      sub: 'merged, split, uploads, web_downloads 폴더의 영상 파일만 표시됩니다. PC에서 바로 올리는 기능은 제공하지 않습니다.',
      action: `<button class="btn primary" onclick="switchTab('download')">먼저 영상 받으러 가기</button>`,
    });
    return;
  }

  host.innerHTML = files.map(file => {
    const selected = state.youtubeUploadSelectedPaths.has(file.path);
    const fileName = file.name || mergeFileName(file.path);
    const topDirectory = String(file.path).split('/')[0];
    const safePathAttribute = escapeHtmlAttribute(file.path);
    const safeNameAttribute = escapeHtmlAttribute(fileName);
    return `<label class="youtube-upload-file-row ${selected ? 'selected' : ''}">
      <span class="selection-control selection-checkbox">
        <input type="checkbox" value="${safePathAttribute}"
               aria-label="${safeNameAttribute} 선택" ${selected ? 'checked' : ''}
               onchange="toggleYouTubeUploadFile(this.value, this.checked)" />
        <span class="selection-mark" aria-hidden="true"></span>
      </span>
      <div class="youtube-upload-file-main">
        <div class="file-name" title="${safePathAttribute}">${escapeHtml(fileName)}</div>
        <div class="youtube-upload-file-path mono">${escapeHtml(file.path)}</div>
      </div>
      <span class="part-chip">${escapeHtml(topDirectory)}</span>
      <span class="file-meta nowrap">${fmtBytes(file.size_bytes)}</span>
      <span class="file-meta nowrap">${fmtAge(file.mtime)}</span>
      <button type="button" class="btn danger sm file-delete-btn" data-path="${safePathAttribute}"
              title="${safeNameAttribute} 삭제"
              aria-label="${safeNameAttribute} 삭제"
              onclick="deleteYouTubeUploadFile(this.dataset.path, event)">✕</button>
    </label>`;
  }).join('');
}

function youtubeUploadFileStem(path) {
  const selectedFile = state.files.find(file => file.path === path);
  const fileName = selectedFile?.name || mergeFileName(path);
  return String(fileName).replace(/\.[^.]+$/, '');
}

/* 파일명에서 확장자와 끝의 HHMMSS를 뗀 제목. */
function youtubeUploadTitleFromPath(path, maxLength = 100) {
  return youtubeUploadFileStem(path)
    .replace(/_([01]\d|2[0-3])[0-5]\d[0-5]\d$/, '')
    .slice(0, maxLength);
}

/* 여러 개를 한꺼번에 올릴 때의 파일별 제목. 기본은 HHMMSS를 뗀 제목이지만, 같은 날
   녹화처럼 제목이 겹치는 파일은 녹화 시각을 남겨 서로 구분한다. */
function youtubeUploadBatchTitles(paths, maxLength = 100) {
  const titleCounts = new Map();
  paths.forEach(path => {
    const title = youtubeUploadTitleFromPath(path, maxLength);
    titleCounts.set(title, (titleCounts.get(title) || 0) + 1);
  });
  return new Map(paths.map(path => {
    const title = youtubeUploadTitleFromPath(path, maxLength);
    return [path, titleCounts.get(title) > 1 ? youtubeUploadFileStem(path).slice(0, maxLength) : title];
  }));
}

function fillYouTubeUploadTitle(path) {
  const titleInput = $('youtube-upload-title');
  if (!titleInput) return;
  const maxLength = titleInput.maxLength > 0 ? titleInput.maxLength : 100;
  titleInput.value = youtubeUploadTitleFromPath(path, maxLength);
}

function toggleYouTubeUploadFile(path, on) {
  if (on) state.youtubeUploadSelectedPaths.add(path);
  else state.youtubeUploadSelectedPaths.delete(path);
  // 방금 체크한 파일이 유일한 선택이 될 때만 제목을 채운다. 체크를 풀어 하나로
  // 돌아온 경우엔 이미 고쳐 둔 제목을 덮어쓰지 않는다.
  if (on && state.youtubeUploadSelectedPaths.size === 1) fillYouTubeUploadTitle(path);
  renderYouTubeUploadFileList();
  renderYouTubeUploadReady();
}

function selectAllYouTubeUploadFiles() {
  const paths = filterYouTubeUploadFiles(state.files).map(file => file.path);
  if (!paths.length) return;
  const allSelected = paths.every(path => state.youtubeUploadSelectedPaths.has(path));
  paths.forEach(path => {
    if (allSelected) state.youtubeUploadSelectedPaths.delete(path);
    else state.youtubeUploadSelectedPaths.add(path);
  });
  if (!allSelected && paths.length === 1) fillYouTubeUploadTitle(paths[0]);
  renderYouTubeUploadFileList();
  renderYouTubeUploadReady();
}

function deleteYouTubeUploadFile(path, event) {
  event?.preventDefault();
  event?.stopPropagation();
  deleteSourceFiles([path], mergeFileName(path));
}

function deleteSelectedYouTubeUploadFiles() {
  return deleteSourceFiles([...state.youtubeUploadSelectedPaths], '선택한 영상');
}

function renderYouTubeUploadReady() {
  const button = $('btn-youtube-upload');
  const bar = $('youtube-upload-ready');
  const text = $('youtube-upload-ready-text');
  const selectedSource = $('youtube-upload-selected-source');
  const titleInput = $('youtube-upload-title');
  if (!button || !bar || !text || !selectedSource || !titleInput) return;

  const status = state.youtubeOAuthStatus;
  const title = titleInput.value.trim();
  const selectedPaths = [...state.youtubeUploadSelectedPaths];
  const selectedCount = selectedPaths.length;
  const single = selectedCount === 1;
  // 여러 개를 골랐을 때는 제목 칸 대신 파일명이 제목이 되므로 입력을 잠근다.
  titleInput.disabled = selectedCount > 1;
  if (single) selectedSource.textContent = selectedPaths[0];
  else if (selectedCount > 1) {
    // 파일마다 붙을 제목을 미리 보여 준다. 같은 제목이 되는 파일은 없는지 여기서 확인할 수 있다.
    const batchTitles = youtubeUploadBatchTitles(selectedPaths);
    const titleItems = selectedPaths.map(path => `<li>${escapeHtml(batchTitles.get(path))}</li>`).join('');
    selectedSource.innerHTML = `${selectedCount}개를 골랐어요. 제목은 파일마다 이렇게 붙습니다.`
      + `<ul class="youtube-selected-source-list">${titleItems}</ul>`;
  } else selectedSource.textContent = '영상을 먼저 골라 주세요.';
  // 경로일 때만 고정폭. 안내문에 mono를 씌우면 한글 사이 공백이 벌어진다.
  selectedSource.classList.toggle('mono', single);

  let blockedReason = '';
  if (!status) blockedReason = 'YouTube 계정 상태를 확인하고 있습니다.';
  else if (status.error) blockedReason = status.error;
  else if (!status.configured) blockedReason = '서버에 YouTube OAuth 설정이 필요합니다.';
  else if (!status.connected) blockedReason = 'YouTube 계정을 연결해 주세요.';
  else if (!selectedCount) blockedReason = '업로드할 서버 영상을 골라 주세요.';
  else if (single && !title) blockedReason = '영상 제목을 입력해 주세요.';

  button.disabled = Boolean(blockedReason);
  bar.classList.toggle('go', !blockedReason);
  $('youtube-upload-step-no')?.classList.toggle('done', !blockedReason);
  if (blockedReason) text.textContent = blockedReason;
  else if (single) text.textContent = `"${title}"을(를) 비공개로 업로드합니다.`;
  else text.textContent = `${selectedCount}개 영상을 파일명 제목으로 비공개 업로드합니다.`;
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

async function submitYouTubeUploadJob(payload) {
  const response = await fetch(`${API}/api/youtube/uploads`, {
    method: 'POST',
    headers: { ...YOUTUBE_MUTATION_HEADERS, 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || 'YouTube 업로드를 등록하지 못했습니다.');
  return data;
}

/* 체크한 파일마다 작업을 하나씩 등록한다. 설명·태그·카테고리·아동용 설정은 공통이고,
   제목은 하나만 골랐을 때만 입력값을 쓴다. 등록된 파일은 체크를 풀어 같은 파일을
   한 번 더 올리는 실수를 막는다. */
async function submitYouTubeUpload(event) {
  event.preventDefault();
  const sources = [...state.youtubeUploadSelectedPaths];
  const single = sources.length === 1;
  const title = $('youtube-upload-title').value.trim();
  if (!sources.length) {
    notify('알림', '업로드할 서버 영상을 골라 주세요.', 'err'); return;
  }
  if (single && !title) {
    notify('알림', '영상 제목을 입력해 주세요.', 'err'); return;
  }
  if (!state.youtubeOAuthStatus?.connected) {
    notify('알림', 'YouTube 계정을 먼저 연결해 주세요.', 'err'); return;
  }

  const sharedMetadata = {
    description: $('youtube-upload-description').value,
    tags: $('youtube-upload-tags').value.split(',').map(tag => tag.trim()).filter(Boolean),
    category_id: $('youtube-upload-category').value,
    made_for_kids: $('youtube-upload-made-for-kids').checked,
  };
  const batchTitles = single ? null : youtubeUploadBatchTitles(sources);
  const button = $('btn-youtube-upload');
  button.disabled = true;
  const submittedJobIds = [];
  const failures = [];
  try {
    for (const [index, source] of sources.entries()) {
      button.textContent = single ? '작업 등록 중…' : `작업 등록 중… (${index + 1}/${sources.length})`;
      try {
        const job = await submitYouTubeUploadJob({
          source,
          title: single ? title : batchTitles.get(source),
          ...sharedMetadata,
        });
        state.youtubeUploadSelectedPaths.delete(source);
        submittedJobIds.push(String(job.id || ''));
      } catch (error) {
        failures.push({
          fileName: mergeFileName(source),
          message: error.message || 'YouTube 업로드를 등록하지 못했습니다.',
        });
      }
    }
    // 토스트는 하나뿐이라 성공·실패를 따로 띄우면 앞 것이 바로 덮인다. 한 줄로 합친다.
    if (!failures.length) {
      const jobLabel = single
        ? (submittedJobIds[0] ? ` ${submittedJobIds[0].slice(0, 8)}` : '')
        : ` ${submittedJobIds.length}개`;
      notify('등록됨', `YouTube 업로드 작업${jobLabel}을 등록했습니다.`, 'ok');
    } else if (single) {
      notify('오류', failures[0].message, 'err');
    } else {
      const registeredNote = submittedJobIds.length ? ` (${submittedJobIds.length}개는 등록됨)` : '';
      notify('오류', `${failures.length}개 등록 실패${registeredNote} · ${failures[0].fileName}: ${failures[0].message}`, 'err');
    }
    if (submittedJobIds.length) loadYouTubeUploadJobs();
  } finally {
    button.textContent = '비공개로 업로드';
    renderYouTubeUploadFileList();
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
    await throwIfResponseFailed(response, 'YouTube 업로드 작업을 불러오지 못했습니다');
    const jobs = await response.json().catch(() => []);
    state.youtubeUploadJobs = Array.isArray(jobs) ? jobs : [];
    renderYouTubeUploadJobs(state.youtubeUploadJobs);
  } catch (error) {
    renderLoadFailure('youtube-upload-jobs', 'YouTube 업로드 작업을 불러오지 못했어요', error);
  }
}

function renderYouTubeUploadJobs(jobs) {
  const host = $('youtube-upload-jobs');
  if (!host) return;
  if (!jobs.length) {
    host.innerHTML = emptyState({
      icon: '⇧',
      title: '아직 YouTube 업로드 작업이 없어요',
      sub: '영상과 정보를 고른 뒤 업로드하면 진행 상황이 여기에 표시됩니다.',
    });
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
          ${videoUrl ? `<a class="btn sm" href="${escapeHtmlAttribute(videoUrl)}" target="_blank" rel="noopener noreferrer">YouTube에서 보기</a>` : ''}
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
    await throwIfResponseFailed(response, 'YouTube 업로드 취소를 요청하지 못했습니다.');
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
