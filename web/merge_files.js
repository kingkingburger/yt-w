
/* ── merge :: file list ────────────────────────────────────────────── */
const FILE_LIST_HOST_IDS = [
  'merge-file-list', 'split-file-list', 'youtube-upload-file-list', 'library-file-list',
];

async function loadFiles(refresh = false) {
  try {
    const query = refresh ? '?refresh=true' : '';
    const r = await fetch(`${API}/api/files${query}`);
    await throwIfResponseFailed(r, '서버 영상 목록을 불러오지 못했습니다');
    state.files = await r.json();
    const validPaths = new Set(state.files.map(f => f.path));
    state.selectedPaths = new Set(
      [...state.selectedPaths].filter(path => validPaths.has(path))
    );
    state.sequence = state.sequence.filter(path => validPaths.has(path));
    if (!validPaths.has(state.splitSelectedPath)) state.splitSelectedPath = null;
    state.youtubeUploadSelectedPaths = new Set(
      [...state.youtubeUploadSelectedPaths].filter(path => validPaths.has(path))
    );
    state.librarySelectedPaths = new Set(
      [...state.librarySelectedPaths].filter(path => validPaths.has(path))
    );
    renderFileList();
    renderSequence();
    renderSplitFileList();
    renderSplitSelection();
    renderYouTubeUploadFileList();
    renderYouTubeUploadReady();
    renderLibrary();
  } catch (error) {
    // 같은 목록을 네 화면이 함께 쓰므로 네 곳 모두에 실패를 알린다.
    FILE_LIST_HOST_IDS.forEach(hostId =>
      renderLoadFailure(hostId, '서버 영상 목록을 불러오지 못했어요', error));
  }
}
function renderFileList() {
  const host = $('merge-file-list');
  const sourceFiles = availableSourceFiles();
  const selectedCount = sourceFiles.filter(file => state.selectedPaths.has(file.path)).length;
  $('merge-file-count').textContent = selectedCount
    ? `${sourceFiles.length}개 · ${selectedCount}개 선택`
    : `${sourceFiles.length}개`;
  const selectAllBtn = $('btn-select-all');
  const sendSelectedBtn = $('btn-send-selected');
  const deleteSelectedBtn = $('btn-delete-selected');
  const deselectAllBtn = $('btn-deselect-all');
  if (selectAllBtn) selectAllBtn.disabled = sourceFiles.length === 0;
  if (selectAllBtn) selectAllBtn.textContent = selectedCount === sourceFiles.length && selectedCount > 0
    ? '전체 해제'
    : '전체 선택';
  if (sendSelectedBtn) sendSelectedBtn.disabled = selectedCount === 0;
  if (deleteSelectedBtn) deleteSelectedBtn.disabled = selectedCount === 0;
  if (deselectAllBtn) deselectAllBtn.disabled = state.sequence.length === 0;
  if (!state.files.length) {
    host.innerHTML = emptyState({
      icon: '⌘',
      title: '아직 받아둔 영상이 없어요',
      sub: '다운로드 탭에서 영상을 받거나, 라이브 녹화가 채널을 녹화하면 여기에 쌓입니다',
      action: `<button class="btn primary" type="button" onclick="switchTab('download')">다운로드 탭으로 가기</button>`,
    });
    return;
  }
  if (!sourceFiles.length) {
    state.sourceGroups = [];
    host.innerHTML = `
      <div class="empty">
        <div class="empty-icon empty-icon-check" aria-hidden="true"></div>
        <div class="empty-title">고를 영상이 더 없어요</div>
        <div class="empty-sub">받아둔 영상을 모두 오른쪽 순서에 넣었습니다</div>
      </div>`;
    return;
  }
  state.sourceGroups = buildFileGroups(sourceFiles);
  host.innerHTML = state.sourceGroups.map((group, groupIdx) => {
    const open = state.sourceGroupOpen.has(group.id);
    const selectedCount = group.paths.filter(path => state.selectedPaths.has(path)).length;
    const allSelected = selectedCount === group.paths.length;
    const someSelected = selectedCount > 0 && !allSelected;
    const sourceBadge = mergeSourceBadge(group.paths[0]);
    const partBadge = group.partLabel ? `<span class="part-chip">${escapeHtml(group.partLabel)}</span>` : '';
    const safeNameAttribute = escapeHtmlAttribute(group.name);
    return `
      <div class="file-group ${open ? 'open' : ''} ${allSelected ? 'selected' : ''}">
        <div class="file-group-head"
             draggable="true"
             ondragstart="sourceGroupDragStart(event, ${groupIdx})"
             ondragend="fileDragEnd(event)"
             onclick="toggleSourceGroup(${groupIdx})">
          <span class="tree-toggle" aria-hidden="true">▸</span>
          <span class="selection-control selection-checkbox">
            <input type="checkbox"
                   aria-label="${safeNameAttribute} 전체 선택"
                   ${allSelected ? 'checked' : ''}
                   ${someSelected ? 'data-partial="true"' : ''}
                   onclick="event.stopPropagation()"
                   onchange="toggleSourceGroupSelect(${groupIdx}, this.checked)" />
            <span class="selection-mark" aria-hidden="true"></span>
          </span>
          <div class="file-group-title" title="${safeNameAttribute}">${escapeHtml(group.name)}</div>
          <div class="file-group-tools">
            ${sourceBadge}
            ${partBadge}
            <div class="file-meta nowrap">${group.paths.length}개 · ${fmtBytes(group.paths.reduce((sum, path) => sum + sizeOfPath(path), 0))}</div>
            <button type="button" class="btn danger sm file-delete-btn" draggable="false"
                    title="${safeNameAttribute} 그룹 전체 삭제"
                    aria-label="${safeNameAttribute} 그룹 전체 삭제"
                    onclick="deleteSourceGroup(${groupIdx}, event)">✕</button>
          </div>
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
  const safePathAttribute = escapeHtmlAttribute(f.path);
  const safeNameAttribute = escapeHtmlAttribute(fname);
  return `
    <label class="file-row child ${checked ? 'selected' : ''}"
           draggable="true"
           data-path="${safePathAttribute}"
           ondragstart="fileDragStart(event, this.dataset.path)"
           ondragend="fileDragEnd(event)">
      <span class="selection-control selection-checkbox">
        <input type="checkbox" value="${safePathAttribute}"
               aria-label="${safeNameAttribute} 선택" ${checked ? 'checked' : ''}
               onchange="toggleFileSelect(this.value, this.checked)" />
        <span class="selection-mark" aria-hidden="true"></span>
      </span>
      <span class="file-grip" aria-hidden="true">::</span>
      <div class="file-name" title="${safeNameAttribute}">${escapeHtml(fname)}</div>
      <div class="file-meta nowrap">${fmtBytes(f.size_bytes)}</div>
      <div class="file-meta nowrap">${fmtAge(f.mtime)}</div>
      <button type="button" class="btn danger sm file-delete-btn" draggable="false" data-path="${safePathAttribute}"
              title="${safeNameAttribute} 삭제"
              aria-label="${safeNameAttribute} 삭제"
              onclick="deleteSourceFile(this.dataset.path, event)">✕</button>
    </label>`;
}
/* 합치기·YouTube 업로드·영상 관리 화면이 같이 쓰는 삭제 경로. label은 파일이
   여럿일 때 개수 앞에 붙을 명사구("선택한 영상")다. 하나면 어느 화면에서
   왔든 파일 이름을 그대로 보여 준다. */
async function deleteSourceFiles(paths, label) {
  const uniquePaths = [...new Set((paths || []).filter(Boolean))];
  if (!uniquePaths.length) return;
  const target = uniquePaths.length === 1
    ? `"${mergeFileName(uniquePaths[0])}" 파일을`
    : `${label || '선택한 영상'} ${uniquePaths.length}개를`;
  if (!confirm(`${target} 삭제할까요?\n삭제한 파일은 복구할 수 없습니다.`)) return;

  try {
    const response = await fetch(`${API}/api/files`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ paths: uniquePaths }),
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(result.detail || '파일 삭제에 실패했습니다');
    await loadFiles(true);
    systemRefresh();
    notify('삭제 완료', `영상 파일 ${result.count}개를 삭제했습니다`, 'ok');
  } catch (error) {
    notify('오류', error.message || '파일 삭제에 실패했습니다', 'err');
  }
}
function deleteSourceFile(path, event) {
  event?.preventDefault();
  event?.stopPropagation();
  deleteSourceFiles([path], mergeFileName(path));
}
function deleteSourceGroup(groupIdx, event) {
  event?.preventDefault();
  event?.stopPropagation();
  const group = state.sourceGroups[groupIdx];
  if (group) deleteSourceFiles(group.paths, `"${group.name}" 그룹의 영상`);
}
function selectedSourcePaths() {
  return buildFileGroups(availableSourceFiles())
    .flatMap(group => group.paths)
    .filter(path => state.selectedPaths.has(path));
}
function deleteSelectedSourceFiles() {
  return deleteSourceFiles(selectedSourcePaths(), '선택한 영상');
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
    group.paths.forEach(path => state.selectedPaths.add(path));
  } else {
    group.paths.forEach(path => state.selectedPaths.delete(path));
  }
  renderFileList();
}
function toggleFileSelect(path, on) {
  if (on) state.selectedPaths.add(path);
  else state.selectedPaths.delete(path);
  renderFileList();
}
function selectAllFiles() {
  const sourceFiles = availableSourceFiles();
  if (!sourceFiles.length) return;
  const paths = buildFileGroups(sourceFiles).flatMap(group => group.paths);
  const allSelected = paths.every(path => state.selectedPaths.has(path));
  paths.forEach(path => {
    if (allSelected) state.selectedPaths.delete(path);
    else state.selectedPaths.add(path);
  });
  renderFileList();
}
function sendSelectedFilesToSequence() {
  return addPathsToSequence(selectedSourcePaths());
}
function deselectAllFiles() {
  state.sequence = [];
  refreshDefaultMergeOutputName();
  renderFileList(); renderSequence();
}
