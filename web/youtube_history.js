/* 업로드 완료 기록과 파일별 상태 표시. */
function youtubeUploadFileStatus(path) {
  const uploaded = state.youtubeUploadHistory?.some(record => record.source === path);
  if (uploaded) return { label: '업로드 완료', kind: 'ok' };
  const jobs = (state.youtubeUploadJobs || []).filter(job => job.source === path);
  if (jobs.some(job => job.status === 'queued' || job.status === 'running')) {
    return { label: '업로드 중', kind: 'warn' };
  }
  if (state.youtubeUploadHistory === null) return { label: '기록 확인 중', kind: 'dim' };
  if (!state.youtubeUploadHistory) return { label: '기록 확인 불가', kind: 'warn' };
  if (jobs[0]?.status === 'failed') return { label: '미업로드 · 실패', kind: 'err' };
  if (jobs[0]?.status === 'cancelled') return { label: '미업로드 · 취소', kind: 'dim' };
  return { label: '미업로드', kind: 'dim' };
}

async function loadYouTubeUploadHistory() {
  try {
    const response = await fetch(`${API}/api/youtube/upload-history`);
    if (!response.ok) throw new Error('업로드 기록 조회 실패');
    const history = await response.json();
    if (!Array.isArray(history)) throw new Error('잘못된 업로드 기록');
    state.youtubeUploadHistory = history;
  } catch (error) {
    state.youtubeUploadHistory = undefined;
  }
  renderYouTubeUploadFileList();
}
