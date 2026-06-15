function formatMergeOutputDate(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function validMergeOutputDate(year, month, day) {
  const date = new Date(year, month - 1, day);
  if (
    date.getFullYear() !== year
    || date.getMonth() !== month - 1
    || date.getDate() !== day
  ) {
    return null;
  }
  return date;
}

function mergeSourceDateCandidates(path, fallbackYear) {
  const value = String(path || '');
  const dates = [];
  const fullDatePattern = /(?:^|[^\d])(\d{4})[-_. ]?(\d{2})[-_. ]?(\d{2})(?=$|[^\d])/g;
  for (const match of value.matchAll(fullDatePattern)) {
    const date = validMergeOutputDate(
      Number(match[1]),
      Number(match[2]),
      Number(match[3]),
    );
    if (date) dates.push(date);
  }

  const shortDatePattern = /(?:^|[^\d])(\d{2})(\d{2})(?=$|[^\d])/g;
  for (const match of value.matchAll(shortDatePattern)) {
    const date = validMergeOutputDate(
      fallbackYear,
      Number(match[1]),
      Number(match[2]),
    );
    if (date) dates.push(date);
  }
  return dates;
}

function earliestMergeSourceDate(paths, fallbackDate = new Date()) {
  const fallbackYear = fallbackDate.getFullYear();
  let earliest = null;
  paths.forEach((path) => {
    mergeSourceDateCandidates(path, fallbackYear).forEach((date) => {
      if (!earliest || date.getTime() < earliest.getTime()) earliest = date;
    });
  });
  return earliest;
}

function defaultMergeOutputName(paths = [], fallbackDate = new Date()) {
  if (paths instanceof Date) return `${formatMergeOutputDate(paths)}.mp4`;
  const sourcePaths = Array.isArray(paths) ? paths : [];
  const sourceDate = earliestMergeSourceDate(sourcePaths, fallbackDate);
  return `${formatMergeOutputDate(sourceDate || fallbackDate)}.mp4`;
}

function syncDefaultMergeOutputName(force, paths = state.sequence) {
  const output = $('merge-output');
  if (!output) return defaultMergeOutputName(paths);
  const next = defaultMergeOutputName(paths);
  const current = output.value.trim();
  const previousDefault = output.dataset.defaultValue || '';
  if (force || !current || current === previousDefault) {
    output.value = next;
  }
  output.dataset.defaultValue = next;
  return next;
}

function setDefaultMergeOutputName(paths = state.sequence) {
  return syncDefaultMergeOutputName(true, paths);
}

function refreshDefaultMergeOutputName(paths = state.sequence) {
  return syncDefaultMergeOutputName(false, paths);
}

function currentMergeOutputName(paths = state.sequence) {
  const output = $('merge-output');
  const value = output.value.trim();
  const next = defaultMergeOutputName(paths);
  if (!value || value === output.dataset.defaultValue) {
    output.value = next;
    output.dataset.defaultValue = next;
    return next;
  }
  return value;
}
