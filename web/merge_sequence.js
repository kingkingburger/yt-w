
/* ── merge :: sequence ─────────────────────────────────────────────── */
function splitMergePath(path) {
  const dirIdx = path.lastIndexOf('/');
  return {
    dir: dirIdx >= 0 ? path.slice(0, dirIdx + 1) : '',
    name: dirIdx >= 0 ? path.slice(dirIdx + 1) : path,
  };
}
function mergeFileName(path) {
  return splitMergePath(path).name;
}
function mergeSourceBadge(path) {
  const source = String(path || '').split('/')[0].toLowerCase();
  if (source !== 'split' && source !== 'merged') return '';
  const label = source === 'merged' ? 'merge' : 'split';
  return `<span class="source-chip ${source}">${label}</span>`;
}
function availableSourceFiles(files = state.files, sequence = state.sequence) {
  const inSequence = new Set(sequence);
  return files.filter(file => !inSequence.has(file.path));
}
function sizeOfPath(path) {
  return state.files.find(file => file.path === path)?.size_bytes || 0;
}
function inferPartGroup(prefix) {
  const cleaned = prefix.replace(/[._\-\s]+$/g, '');
  const tokens = cleaned.split(/[._\-\s]+/).filter(Boolean);
  if (tokens.length >= 2) {
    const dateToken = tokens[tokens.length - 2];
    const timeToken = tokens[tokens.length - 1];
    if (/^\d{8}$/.test(dateToken) && /^\d{6}$/.test(timeToken)) {
      return `${dateToken}_${timeToken}`;
    }
  }

  const last = tokens[tokens.length - 1] || cleaned || prefix;
  const hashLike = /^[A-Fa-f0-9]{8,}$/.test(last)
    || (/^[A-Za-z0-9_-]{6,}$/.test(last) && /[A-Za-z]/.test(last) && /\d/.test(last))
    || /^\d{10,}$/.test(last);
  return hashLike ? last : cleaned;
}
function getPartInfo(path) {
  const { dir, name } = splitMergePath(path);
  const match = name.match(/^(.*?)(?:[._\-\s]?part[._\-\s]*)(\d+)(.*)$/i);
  if (!match) return null;
  const number = Number(match[2]);
  if (!Number.isFinite(number)) return null;
  const prefix = match[1];
  const suffix = match[3];
  const group = inferPartGroup(prefix);
  return {
    path,
    dir,
    prefix,
    suffix,
    group,
    /* 묶는 기준(group)은 날짜·시간까지만 좁히지만, 화면에 띄우는 이름은
       접두사 전체를 쓴다. "20260804_210000"만 보여주면 어느 채널의 녹화인지
       알 수 없다. */
    label: prefix.replace(/[._\-\s]+$/g, '') || group,
    number,
    rawNumber: match[2],
    key: `${dir}\u0000${group.toLowerCase()}\u0000${suffix.toLowerCase()}`,
  };
}
function getPartRun(path, filePaths = state.files.map(f => f.path)) {
  const info = getPartInfo(path);
  if (!info) return [path];

  const byNumber = new Map();
  filePaths.forEach(candidate => {
    const candidateInfo = getPartInfo(candidate);
    if (!candidateInfo || candidateInfo.key !== info.key) return;
    if (!byNumber.has(candidateInfo.number)) byNumber.set(candidateInfo.number, candidate);
  });

  let start = info.number;
  while (byNumber.has(start - 1)) start -= 1;
  let end = info.number;
  while (byNumber.has(end + 1)) end += 1;

  const run = [];
  for (let n = start; n <= end; n += 1) {
    const candidate = byNumber.get(n);
    if (!candidate) break;
    run.push(candidate);
  }
  return run.length > 1 ? run : [path];
}
function getPartRunLabel(path, filePaths = state.files.map(f => f.path)) {
  const run = getPartRun(path, filePaths);
  if (run.length < 2) return '';
  const infos = run.map(getPartInfo).filter(Boolean);
  const width = Math.max(...infos.map(info => info.rawNumber.length));
  const nums = infos.map(info => info.number);
  const first = String(Math.min(...nums)).padStart(width, '0');
  const last = String(Math.max(...nums)).padStart(width, '0');
  const label = infos[0]?.label || '';
  return label ? `${label} · part ${first}-${last}` : `part ${first}-${last}`;
}
function getPartRangeLabel(paths) {
  const infos = paths.map(getPartInfo).filter(Boolean);
  if (!infos.length) return '';
  const width = Math.max(...infos.map(info => info.rawNumber.length));
  const nums = infos.map(info => info.number);
  const first = String(Math.min(...nums)).padStart(width, '0');
  const last = String(Math.max(...nums)).padStart(width, '0');
  return `part ${first}-${last}`;
}
function buildFileGroups(files = state.files) {
  const groups = [];
  const byId = new Map();

  files.forEach((file) => {
    const info = getPartInfo(file.path);
    const id = info ? info.key : `file:${file.path}`;
    let group = byId.get(id);
    if (!group) {
      group = {
        id,
        key: info?.key || id,
        name: info?.label || mergeFileName(file.path),
        isPartGroup: Boolean(info),
        files: [],
        paths: [],
      };
      byId.set(id, group);
      groups.push(group);
    }
    group.files.push({ ...file, partInfo: info });
    group.paths.push(file.path);
  });

  groups.forEach((group) => {
    if (!group.isPartGroup) return;
    group.files.sort((a, b) => {
      const byPart = (a.partInfo?.number ?? 0) - (b.partInfo?.number ?? 0);
      return byPart || a.path.localeCompare(b.path, 'ko', { numeric: true, sensitivity: 'base' });
    });
    group.paths = group.files.map(file => file.path);
    group.partLabel = getPartRangeLabel(group.paths);
  });

  return groups;
}
function addPathsToSequence(paths, insertAt = state.sequence.length) {
  const existing = new Set(state.sequence);
  const uniquePaths = [];
  paths.forEach(path => {
    if (existing.has(path)) return;
    existing.add(path);
    uniquePaths.push(path);
  });
  if (!uniquePaths.length) return 0;

  const target = Math.max(0, Math.min(insertAt, state.sequence.length));
  state.sequence.splice(target, 0, ...uniquePaths);
  uniquePaths.forEach(path => state.selectedPaths.delete(path));
  refreshDefaultMergeOutputName();
  renderFileList();
  renderSequence();
  return uniquePaths.length;
}
function getSequencePartBlock(idx) {
  const path = state.sequence[idx];
  const info = getPartInfo(path);
  if (!info) return { start: idx, end: idx };

  let start = idx;
  while (start > 0) {
    const prev = getPartInfo(state.sequence[start - 1]);
    const current = getPartInfo(state.sequence[start]);
    if (!prev || !current || prev.key !== info.key || prev.number !== current.number - 1) break;
    start -= 1;
  }

  let end = idx;
  while (end < state.sequence.length - 1) {
    const current = getPartInfo(state.sequence[end]);
    const next = getPartInfo(state.sequence[end + 1]);
    if (!current || !next || next.key !== info.key || next.number !== current.number + 1) break;
    end += 1;
  }

  return { start, end };
}
function moveSequenceBlock(start, end, dropIdx) {
  if (dropIdx >= start && dropIdx <= end + 1) return false;
  const count = end - start + 1;
  const moved = state.sequence.splice(start, count);
  const insertAt = dropIdx > start ? dropIdx - count : dropIdx;
  state.sequence.splice(insertAt, 0, ...moved);
  return true;
}
function buildSequenceRows(mode = state.sequenceViewMode) {
  const rows = [];
  for (let idx = 0; idx < state.sequence.length; idx += 1) {
    const block = mode === 'compact' ? getSequencePartBlock(idx) : { start: idx, end: idx };
    const start = block.start;
    const end = block.end;
    rows.push({
      start,
      end,
      paths: state.sequence.slice(start, end + 1),
    });
    idx = end;
  }
  return rows;
}
function formatPartRangeName(paths) {
  const first = getPartInfo(paths[0]);
  const last = getPartInfo(paths[paths.length - 1]);
  if (!first || !last || first.key !== last.key) return '';
  const width = Math.max(first.rawNumber.length, last.rawNumber.length);
  const firstNum = String(first.number).padStart(width, '0');
  const lastNum = String(last.number).padStart(width, '0');
  return `${first.label} · part ${firstNum}-${lastNum}${first.suffix}`;
}
function sequenceRowName(row) {
  if (row.paths.length === 1) return mergeFileName(row.paths[0]);
  return formatPartRangeName(row.paths)
    || `${mergeFileName(row.paths[0])} - ${mergeFileName(row.paths[row.paths.length - 1])}`;
}
function setSequenceViewMode(mode) {
  state.sequenceViewMode = mode === 'full' ? 'full' : 'compact';
  renderSequence();
}
function renderSequence() {
  const host = $('merge-seq-list');
  host.ondragover = seqListDragOver;
  host.ondragleave = seqListDragLeave;
  host.ondrop = seqListDrop;
  const rows = buildSequenceRows();
  $('merge-seq-count').textContent = state.sequenceViewMode === 'compact' && rows.length !== state.sequence.length
    ? `${state.sequence.length}개 클립 · ${rows.length}줄`
    : `${state.sequence.length}개 클립`;
  const compactBtn = $('seq-view-compact');
  const fullBtn = $('seq-view-full');
  if (compactBtn) compactBtn.classList.toggle('active', state.sequenceViewMode === 'compact');
  if (fullBtn) fullBtn.classList.toggle('active', state.sequenceViewMode === 'full');
  const sortBtn = $('btn-sort-sequence-name');
  if (sortBtn) sortBtn.disabled = state.sequence.length < 2;
  renderMergeStrip();
  renderMergeReady();
  if (!state.sequence.length) {
    host.classList.add('empty-seq');
    host.innerHTML = '왼쪽 목록에서 영상을 고르면 고른 순서대로 여기에 쌓입니다.<br />끌어서 순서를 바꿀 수 있어요.';
    return;
  }
  host.classList.remove('empty-seq');
  host.innerHTML = rows.map((row) => {
    const fname = sequenceRowName(row);
    const blockSize = row.end - row.start + 1;
    const blockLabel = blockSize > 1 ? getPartRunLabel(row.paths[0], row.paths) : '';
    const blockBadge = blockLabel ? `<span class="seq-badge">${escapeHtml(blockLabel)}</span>` : '';
    const sourceBadge = mergeSourceBadge(row.paths[0]);
    const badges = sourceBadge || blockBadge
      ? `<div class="seq-badges">${sourceBadge}${blockBadge}</div>`
      : '';
    const idxLabel = blockSize > 1
      ? `${String(row.start + 1).padStart(2, '0')}-${String(row.end + 1).padStart(2, '0')}`
      : String(row.start + 1).padStart(2, '0');
    const title = row.paths.map(mergeFileName).join('\n');
    const removeAction = blockSize > 1
      ? `removeSeqBlock(${row.start}, ${row.end})`
      : `removeSeqItem(${row.start})`;
    return `
      <div class="seq-item ${blockSize > 1 ? 'part-block' : ''}" draggable="true" data-idx="${row.start}"
           ondragstart="seqDragStart(event, ${row.start})"
           ondragover="seqDragOver(event, ${row.start})"
           ondragleave="seqDragLeave(event, ${row.start})"
           ondrop="seqDrop(event, ${row.start})"
           ondragend="seqDragEnd(event)">
        <div class="grip">⋮⋮</div>
        <div class="idx">${idxLabel}</div>
        <div class="name" title="${escapeHtml(title)}">${escapeHtml(fname)}${badges}</div>
        <button class="btn sm danger" aria-label="${escapeHtml(fname)} 목록에서 빼기"
                onclick="${removeAction}">✕</button>
      </div>`;
  }).join('');
}

/* ── merge :: 결과 미리보기 스트립 ─────────────────────────────────── */
/* 조각을 하나로 붙이는 게 이 화면의 본론이라, 실행 전에 결과를 한 줄로 본다.
   폭은 용량 비율이다. 재생 길이는 서버가 알려주지 않으므로 그렇게 표기한다. */
function renderMergeStrip() {
  const track = $('merge-strip-track');
  const total = $('merge-strip-total');
  const note = $('merge-strip-note');
  if (!track) return;

  const totalBytes = state.sequence.reduce((sum, path) => sum + sizeOfPath(path), 0);
  if (!state.sequence.length) {
    track.className = 'strip-track empty';
    track.textContent = '고른 영상이 여기에 순서대로 이어 붙습니다';
    total.textContent = '클립 없음';
    note.style.display = 'none';
    return;
  }

  note.style.display = '';
  total.textContent = `${state.sequence.length}개 클립 · ${fmtBytes(totalBytes)}`;
  track.className = 'strip-track';
  track.innerHTML = state.sequence.map((path, index) => {
    const bytes = sizeOfPath(path);
    const share = totalBytes > 0 ? bytes / totalBytes : 1 / state.sequence.length;
    const label = String(index + 1).padStart(2, '0');
    return `
      <div class="strip-block" style="flex: ${Math.max(share, 0.001)} 1 0"
           title="${escapeHtml(mergeFileName(path))} · ${fmtBytes(bytes)}"
           onmouseenter="highlightSeqIndex(${index}, true)"
           onmouseleave="highlightSeqIndex(${index}, false)">${label}</div>`;
  }).join('');
}
function highlightSeqIndex(index, on) {
  const rows = buildSequenceRows();
  const row = rows.find(item => index >= item.start && index <= item.end);
  if (!row) return;
  document.querySelector(`.seq-item[data-idx="${row.start}"]`)?.classList.toggle('hot', on);
}

/* ── merge :: 실행 준비 상태 ───────────────────────────────────────── */
/* 못 누르는 이유를 버튼을 누르기 전에 말한다. */
function renderMergeReady() {
  const bar = $('merge-ready');
  const text = $('merge-ready-text');
  const button = $('btn-execute-merge');
  const stepNo = $('merge-step-no');
  if (!bar || !text || !button) return;

  const outputName = ($('merge-output')?.value || '').trim();
  const totalBytes = state.sequence.reduce((sum, path) => sum + sizeOfPath(path), 0);
  const modeLabel = state.mergeMode === 'concat' ? '빠르게' : '재인코딩';

  let blockedReason = '';
  if (state.sequence.length === 0) blockedReason = '체크한 영상을 보내기로 2개 이상 넣어 주세요.';
  else if (state.sequence.length === 1) blockedReason = '영상이 1개뿐입니다. 하나 더 고르면 합칠 수 있어요.';
  else if (!outputName) blockedReason = '저장할 파일 이름을 입력해 주세요.';

  button.disabled = Boolean(blockedReason);
  bar.classList.toggle('go', !blockedReason);
  if (stepNo) stepNo.classList.toggle('done', !blockedReason);
  text.innerHTML = blockedReason
    ? escapeHtml(blockedReason)
    : `${state.sequence.length}개 클립 ${fmtBytes(totalBytes)}를 <strong>${escapeHtml(outputName)}</strong> 하나로 ${modeLabel} 합칩니다.`;
}
function clearSequence() {
  deselectAllFiles();
}
function removeSeqItem(idx) {
  removeSeqBlock(idx, idx);
}
function removeSeqBlock(start, end) {
  const count = end - start + 1;
  state.sequence.splice(start, count);
  refreshDefaultMergeOutputName();
  renderFileList(); renderSequence();
}
function sortSequenceByName() {
  state.sequence.sort((a, b) => {
    const aName = a.split('/').pop() || a;
    const bName = b.split('/').pop() || b;
    const byName = aName.localeCompare(bName, 'ko', { numeric: true, sensitivity: 'base' });
    return byName || a.localeCompare(b, 'ko', { numeric: true, sensitivity: 'base' });
  });
  renderSequence();
}
let dragSrc = null;
let mergeDrag = null;
function clearMergeDragUi() {
  document.querySelectorAll('.seq-item').forEach(el => {
    el.classList.remove('dragging', 'drop-target', 'moving-block');
  });
  document.querySelectorAll('.file-row').forEach(el => el.classList.remove('dragging'));
  document.querySelectorAll('.file-group').forEach(el => el.classList.remove('dragging'));
  document.querySelectorAll('.seq-list').forEach(el => el.classList.remove('drop-ready'));
}
function fileDragStart(e, path) {
  const paths = getPartRun(path);
  mergeDrag = { type: 'file', paths };
  dragSrc = null;
  e.currentTarget.classList.add('dragging');
  e.dataTransfer.effectAllowed = 'copyMove';
  e.dataTransfer.setData('text/plain', paths.join('\n'));
}
function sourceGroupDragStart(e, groupIdx) {
  const group = state.sourceGroups[groupIdx];
  if (!group) return;
  mergeDrag = { type: 'file', paths: [...group.paths] };
  dragSrc = null;
  e.currentTarget.closest('.file-group')?.classList.add('dragging');
  e.dataTransfer.effectAllowed = 'copyMove';
  e.dataTransfer.setData('text/plain', group.paths.join('\n'));
}
function fileDragEnd() {
  clearMergeDragUi();
  mergeDrag = null;
}
function seqDragStart(e, idx) {
  const block = getSequencePartBlock(idx);
  dragSrc = idx;
  mergeDrag = {
    type: 'sequence',
    start: block.start,
    end: block.end,
    paths: state.sequence.slice(block.start, block.end + 1),
  };
  e.currentTarget.classList.add('dragging');
  document.querySelectorAll('.seq-item').forEach((el) => {
    const itemIdx = Number(el.dataset.idx);
    if (itemIdx >= block.start && itemIdx <= block.end) el.classList.add('moving-block');
  });
  e.dataTransfer.effectAllowed = 'move';
  e.dataTransfer.setData('text/plain', mergeDrag.paths.join('\n'));
}
function seqDragOver(e, idx) {
  e.preventDefault();
  e.stopPropagation();
  e.dataTransfer.dropEffect = mergeDrag?.type === 'file' ? 'copy' : 'move';
  const inMovingBlock = mergeDrag?.type === 'sequence'
    && idx >= mergeDrag.start
    && idx <= mergeDrag.end;
  if (!inMovingBlock) e.currentTarget.classList.add('drop-target');
}
function seqDragLeave(e) { e.currentTarget.classList.remove('drop-target'); }
function seqDrop(e, idx) {
  e.preventDefault();
  e.stopPropagation();
  if (!mergeDrag) return;

  if (mergeDrag.type === 'file') {
    addPathsToSequence(mergeDrag.paths, idx);
  } else if (mergeDrag.type === 'sequence') {
    if (moveSequenceBlock(mergeDrag.start, mergeDrag.end, idx)) renderSequence();
  }
  clearMergeDragUi();
  mergeDrag = null;
  dragSrc = null;
}
function seqListDragOver(e) {
  if (!mergeDrag) return;
  e.preventDefault();
  e.dataTransfer.dropEffect = mergeDrag.type === 'file' ? 'copy' : 'move';
  e.currentTarget.classList.add('drop-ready');
}
function seqListDragLeave(e) {
  if (!e.currentTarget.contains(e.relatedTarget)) e.currentTarget.classList.remove('drop-ready');
}
function seqListDrop(e) {
  e.preventDefault();
  if (!mergeDrag || e.target.closest('.seq-item')) return;

  if (mergeDrag.type === 'file') {
    addPathsToSequence(mergeDrag.paths);
  } else if (mergeDrag.type === 'sequence') {
    if (moveSequenceBlock(mergeDrag.start, mergeDrag.end, state.sequence.length)) renderSequence();
  }
  clearMergeDragUi();
  mergeDrag = null;
  dragSrc = null;
}
function seqDragEnd() {
  clearMergeDragUi();
  mergeDrag = null;
  dragSrc = null;
}
