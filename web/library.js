/* ── 영상 관리 ────────────────────────────────────────────────────── */
/* 서버에 쌓인 영상을 폴더별로 보고 지우는 화면. 합치기·나누기·업로드 화면은
   목적에 맞게 목록을 거르지만, 여기서는 다운로드 폴더의 영상이 전부 보인다.
   삭제는 합치기 화면과 같은 경로(deleteSourceFiles)를 그대로 쓴다. */
function buildLibraryGroups(files) {
  const groups = [];
  const byDirectory = new Map();
  files.forEach(file => {
    const directory = splitMergePath(file.path).dir;
    let group = byDirectory.get(directory);
    if (!group) {
      group = {
        id: directory,
        name: directory.replace(/\/$/, '') || '/',
        files: [],
        paths: [],
        sizeBytes: 0,
      };
      byDirectory.set(directory, group);
      groups.push(group);
    }
    group.files.push(file);
    group.paths.push(file.path);
    group.sizeBytes += file.size_bytes || 0;
  });
  return groups.sort((a, b) => a.id.localeCompare(b.id, 'ko', { numeric: true, sensitivity: 'base' }));
}

function libraryVisibleFiles() {
  return filterSplitFiles(state.files, state.librarySearchQuery);
}

function renderLibrary() {
  const host = $('library-file-list');
  if (!host) return;
  const visibleFiles = libraryVisibleFiles();
  const selectedFiles = state.files.filter(file => state.librarySelectedPaths.has(file.path));
  const totalBytes = state.files.reduce((sum, file) => sum + (file.size_bytes || 0), 0);
  const selectedBytes = selectedFiles.reduce((sum, file) => sum + (file.size_bytes || 0), 0);
  $('library-file-count').textContent = selectedFiles.length
    ? `${state.files.length}개 · ${selectedFiles.length}개 선택 · ${fmtBytes(selectedBytes)}`
    : `${state.files.length}개 · ${fmtBytes(totalBytes)}`;

  const selectAllButton = $('btn-library-select-all');
  const deleteSelectedButton = $('btn-library-delete-selected');
  const allVisibleSelected = visibleFiles.length > 0
    && visibleFiles.every(file => state.librarySelectedPaths.has(file.path));
  if (selectAllButton) {
    selectAllButton.disabled = visibleFiles.length === 0;
    selectAllButton.textContent = allVisibleSelected ? '전체 해제' : '전체 선택';
  }
  if (deleteSelectedButton) deleteSelectedButton.disabled = selectedFiles.length === 0;

  if (!state.files.length) {
    state.libraryGroups = [];
    host.innerHTML = emptyState({
      icon: '⌘',
      title: '서버에 영상이 없어요',
      sub: '다운로드 탭에서 영상을 받거나, 라이브 녹화가 채널을 녹화하면 여기에 쌓입니다',
      action: `<button class="btn primary" type="button" onclick="switchTab('download')">다운로드 탭으로 가기</button>`,
    });
    return;
  }
  if (!visibleFiles.length) {
    state.libraryGroups = [];
    host.innerHTML = emptyState({
      icon: '⌕',
      title: '검색 결과가 없어요',
      sub: '다른 파일명이나 폴더 이름으로 검색해 주세요',
    });
    return;
  }

  state.libraryGroups = buildLibraryGroups(visibleFiles);
  host.innerHTML = state.libraryGroups.map((group, groupIdx) => {
    const open = state.libraryGroupOpen.has(group.id) || Boolean(state.librarySearchQuery);
    const selectedCount = group.paths.filter(path => state.librarySelectedPaths.has(path)).length;
    const allSelected = selectedCount === group.paths.length;
    const someSelected = selectedCount > 0 && !allSelected;
    const safeNameAttribute = escapeHtmlAttribute(group.name);
    return `
      <div class="file-group ${open ? 'open' : ''} ${allSelected ? 'selected' : ''}">
        <div class="file-group-head library-file-group-head" onclick="toggleLibraryGroup(${groupIdx})">
          <span class="tree-toggle" aria-hidden="true">▸</span>
          <span class="selection-control selection-checkbox">
            <input type="checkbox"
                   aria-label="${safeNameAttribute} 폴더 전체 선택"
                   ${allSelected ? 'checked' : ''}
                   ${someSelected ? 'data-partial="true"' : ''}
                   onclick="event.stopPropagation()"
                   onchange="toggleLibraryGroupSelect(${groupIdx}, this.checked)" />
            <span class="selection-mark" aria-hidden="true"></span>
          </span>
          <div class="file-group-title" title="${safeNameAttribute}">${escapeHtml(group.name)}</div>
          <div class="file-group-tools">
            <div class="file-meta nowrap">${group.paths.length}개 · ${fmtBytes(group.sizeBytes)}</div>
            <button type="button" class="btn danger sm file-delete-btn"
                    title="${safeNameAttribute} 폴더의 영상 전체 삭제"
                    aria-label="${safeNameAttribute} 폴더의 영상 전체 삭제"
                    onclick="deleteLibraryGroup(${groupIdx}, event)">✕</button>
          </div>
        </div>
        <div class="file-group-children">
          ${group.files.map(file => renderLibraryFileRow(file)).join('')}
        </div>
      </div>`;
  }).join('');
  host.querySelectorAll('input[data-partial="true"]').forEach(input => {
    input.indeterminate = true;
  });
}

function renderLibraryFileRow(file) {
  const checked = state.librarySelectedPaths.has(file.path);
  const fileName = file.name || mergeFileName(file.path);
  const safePathAttribute = escapeHtmlAttribute(file.path);
  const safeNameAttribute = escapeHtmlAttribute(fileName);
  return `
    <label class="file-row child library-file-row ${checked ? 'selected' : ''}">
      <span class="selection-control selection-checkbox">
        <input type="checkbox" value="${safePathAttribute}"
               aria-label="${safeNameAttribute} 선택" ${checked ? 'checked' : ''}
               onchange="toggleLibraryFile(this.value, this.checked)" />
        <span class="selection-mark" aria-hidden="true"></span>
      </span>
      <div class="file-name" title="${safePathAttribute}">${escapeHtml(fileName)}</div>
      <div class="file-meta nowrap">${fmtBytes(file.size_bytes)}</div>
      <div class="file-meta nowrap">${fmtAge(file.mtime)}</div>
      <button type="button" class="btn danger sm file-delete-btn" data-path="${safePathAttribute}"
              title="${safeNameAttribute} 삭제"
              aria-label="${safeNameAttribute} 삭제"
              onclick="deleteLibraryFile(this.dataset.path, event)">✕</button>
    </label>`;
}

function toggleLibraryGroup(groupIdx) {
  const group = state.libraryGroups[groupIdx];
  if (!group) return;
  if (state.libraryGroupOpen.has(group.id)) state.libraryGroupOpen.delete(group.id);
  else state.libraryGroupOpen.add(group.id);
  renderLibrary();
}

function toggleLibraryGroupSelect(groupIdx, on) {
  const group = state.libraryGroups[groupIdx];
  if (!group) return;
  if (on) group.paths.forEach(path => state.librarySelectedPaths.add(path));
  else group.paths.forEach(path => state.librarySelectedPaths.delete(path));
  renderLibrary();
}

function toggleLibraryFile(path, on) {
  if (on) state.librarySelectedPaths.add(path);
  else state.librarySelectedPaths.delete(path);
  renderLibrary();
}

/* 검색 중이면 보이는 파일만 고른다. "20260818"로 좁힌 뒤 전체 선택 → 삭제가
   이 화면의 주된 쓰임새다. */
function selectAllLibraryFiles() {
  const paths = libraryVisibleFiles().map(file => file.path);
  if (!paths.length) return;
  const allSelected = paths.every(path => state.librarySelectedPaths.has(path));
  paths.forEach(path => {
    if (allSelected) state.librarySelectedPaths.delete(path);
    else state.librarySelectedPaths.add(path);
  });
  renderLibrary();
}

function setLibrarySearch(query) {
  state.librarySearchQuery = query || '';
  renderLibrary();
}

function deleteLibraryFile(path, event) {
  event?.preventDefault();
  event?.stopPropagation();
  deleteSourceFiles([path], mergeFileName(path));
}

function deleteLibraryGroup(groupIdx, event) {
  event?.preventDefault();
  event?.stopPropagation();
  const group = state.libraryGroups[groupIdx];
  if (group) deleteSourceFiles(group.paths, `"${group.name}" 폴더의 영상`);
}

function deleteSelectedLibraryFiles() {
  return deleteSourceFiles([...state.librarySelectedPaths], '선택한 영상');
}
