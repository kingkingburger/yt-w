
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
    host.innerHTML = emptyState({
      icon: '⇧',
      title: '업로드할 서버 영상이 없어요',
      sub: 'merged, split, uploads, web_downloads 폴더의 영상 파일만 표시됩니다. PC에서 바로 올리는 기능은 제공하지 않습니다.',
      action: `<button class="btn primary" onclick="switchTab('download')">먼저 영상 받으러 가기</button>`,
    });
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
  const selectedFile = filterYouTubeUploadFiles(state.files).find(file => file.path === path);
  state.youtubeUploadSelectedPath = selectedFile?.path || null;
  const titleInput = $('youtube-upload-title');
  if (titleInput) {
    const fileName = selectedFile ? selectedFile.name || mergeFileName(selectedFile.path) : '';
    const maxLength = titleInput.maxLength > 0 ? titleInput.maxLength : 100;
    const uploadTitle = String(fileName)
      .replace(/\.[^.]+$/, '')
      .replace(/_([01]\d|2[0-3])[0-5]\d[0-5]\d$/, '');
    titleInput.value = uploadTitle.slice(0, maxLength);
  }
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
  // 경로일 때만 고정폭. 안내문에 mono를 씌우면 한글 사이 공백이 벌어진다.
  selectedSource.classList.toggle('mono', Boolean(selected));

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
