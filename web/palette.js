/* Video-inspired color palette picker. */
const PALETTE_STORAGE_KEY = 'yt-w.palette.v1';
const DEFAULT_PALETTE_ID = 'studio';
const PALETTES = Object.freeze([
  Object.freeze({
    id: 'sage-blush',
    name: '세이지 블러시',
    sourceName: '세이지그린 + 연분홍',
    category: 'soft',
    colors: Object.freeze(['#719470', '#E0B3B6']),
    mood: '우아한 빈티지',
  }),
  Object.freeze({
    id: 'ivory-sky',
    name: '아이보리 스카이',
    sourceName: '아이보리 + 연하늘',
    category: 'soft',
    colors: Object.freeze(['#F5ECC2', '#A7D4E4']),
    mood: '맑고 부드러운 여름',
  }),
  Object.freeze({
    id: 'orange-teal',
    name: '오렌지 틸',
    sourceName: '오렌지 + 틸블루',
    category: 'vivid',
    colors: Object.freeze(['#D96629', '#0093A5']),
    mood: '강렬한 시네마틱',
  }),
  Object.freeze({
    id: 'rose-mint',
    name: '로즈 민트',
    sourceName: '로즈핑크 + 민트그린',
    category: 'vivid',
    colors: Object.freeze(['#CF445B', '#2CC79B']),
    mood: '발랄한 트로피컬',
  }),
  Object.freeze({
    id: 'coffee-olive',
    name: '커피 올리브',
    sourceName: '커피브라운 + 올리브그린',
    category: 'earth',
    colors: Object.freeze(['#71502F', '#788B60']),
    mood: '차분한 헤리티지',
  }),
  Object.freeze({
    id: 'magenta-blue',
    name: '마젠타 블루',
    sourceName: '자홍 + 진파랑',
    category: 'vivid',
    colors: Object.freeze(['#B73F74', '#005B8D']),
    mood: '도시적인 저녁',
  }),
  Object.freeze({
    id: 'lime-purple',
    name: '라임 퍼플',
    sourceName: '라임옐로우 + 진보라',
    category: 'vivid',
    colors: Object.freeze(['#C7D14F', '#501345']),
    mood: '대담하고 실험적',
  }),
  Object.freeze({
    id: 'pale-yellow-dark-olive',
    name: '페일 올리브',
    sourceName: '연노랑 + 다크올리브',
    category: 'earth',
    colors: Object.freeze(['#FFEFAE', '#42533E']),
    mood: '조용한 자연광',
  }),
  Object.freeze({
    id: 'amber-coffee',
    name: '앰버 커피',
    sourceName: '앰버 + 커피브라운',
    category: 'earth',
    colors: Object.freeze(['#EC9F59', '#6D4F2D']),
    mood: '따뜻하고 달콤함',
  }),
  Object.freeze({
    id: 'apricot-blue',
    name: '애프리콧 블루',
    sourceName: '살구 + 파랑',
    category: 'soft',
    colors: Object.freeze(['#FDD4BD', '#006EB8']),
    mood: '친밀함과 신뢰',
  }),
  Object.freeze({
    id: 'ochre-lavender',
    name: '오커 라벤더',
    sourceName: '황토 + 라벤더',
    category: 'earth',
    colors: Object.freeze(['#C27544', '#B5B1D8']),
    mood: '몽환적인 레트로',
  }),
  Object.freeze({
    id: 'terracotta-dusty-rose',
    name: '테라코타 로즈',
    sourceName: '테라코타 + 회분홍',
    category: 'soft',
    colors: Object.freeze(['#C55347', '#C0A9B3']),
    mood: '성숙한 빈티지',
  }),
  Object.freeze({
    id: 'pine-navy',
    name: '파인 네이비',
    sourceName: '솔잎색 + 감청',
    category: 'earth',
    colors: Object.freeze(['#437742', '#064F6E']),
    mood: '깊고 고요한 숲',
  }),
  Object.freeze({
    id: 'jade-lavender',
    name: '제이드 라벤더',
    sourceName: '옥색 + 라벤더',
    category: 'soft',
    colors: Object.freeze(['#22A68E', '#B4ADD7']),
    mood: '서늘하고 몽환적',
  }),
  Object.freeze({
    id: 'red-black-green',
    name: '크림슨 포레스트',
    sourceName: '빨강 + 흑녹',
    category: 'vivid',
    colors: Object.freeze(['#BF0836', '#0E1C0F']),
    mood: '비장하고 치명적',
  }),
  Object.freeze({
    id: 'coral-midnight',
    name: '코럴 미드나이트',
    sourceName: '코럴 + 미드나잇블루',
    category: 'vivid',
    colors: Object.freeze(['#EC7766', '#05102C']),
    mood: '서정적인 밤',
  }),
]);

let appliedPaletteId = DEFAULT_PALETTE_ID;
let previewPaletteId = DEFAULT_PALETTE_ID;
let activePaletteCategory = 'all';
let paletteReturnFocus = null;

function paletteById(paletteId) {
  return PALETTES.find(palette => palette.id === paletteId) || null;
}

function validPaletteId(paletteId) {
  return paletteId === DEFAULT_PALETTE_ID || paletteById(paletteId) !== null;
}

function storedPaletteId(storage) {
  try {
    const paletteId = storage.getItem(PALETTE_STORAGE_KEY);
    return validPaletteId(paletteId) ? paletteId : DEFAULT_PALETTE_ID;
  } catch (_error) {
    return DEFAULT_PALETTE_ID;
  }
}

function persistPaletteId(paletteId, storage) {
  try {
    if (paletteId === DEFAULT_PALETTE_ID) storage.removeItem(PALETTE_STORAGE_KEY);
    else storage.setItem(PALETTE_STORAGE_KEY, paletteId);
    return true;
  } catch (_error) {
    return false;
  }
}

function setDocumentPalette(paletteId, root = document.documentElement) {
  const nextPaletteId = validPaletteId(paletteId) ? paletteId : DEFAULT_PALETTE_ID;
  root.dataset.palette = nextPaletteId;
  return nextPaletteId;
}

function paletteDisplayName(paletteId) {
  return paletteById(paletteId)?.name || 'Studio 기본';
}

function paletteColors(paletteId) {
  return paletteById(paletteId)?.colors || ['#6847ED', '#CAFF58'];
}

function paletteSwatchesMarkup(paletteId) {
  return paletteColors(paletteId)
    .map(color => `<span style="--palette-swatch:${escapeHtmlAttribute(color)}"></span>`)
    .join('');
}

function renderPaletteTrigger() {
  const name = $('palette-trigger-name');
  const swatches = $('palette-trigger-swatches');
  if (name) name.textContent = paletteDisplayName(appliedPaletteId);
  if (swatches) swatches.innerHTML = paletteSwatchesMarkup(appliedPaletteId);
}

function visiblePalettes(category = activePaletteCategory) {
  if (category === 'all') return PALETTES;
  return PALETTES.filter(palette => palette.category === category);
}

function renderPalettePicker() {
  document.querySelectorAll('[data-palette-category]').forEach((button) => {
    button.classList.toggle('active', button.dataset.paletteCategory === activePaletteCategory);
  });

  const grid = $('palette-grid');
  if (!grid) return;
  grid.innerHTML = visiblePalettes().map((palette) => {
    const selected = palette.id === previewPaletteId;
    return `<button type="button" class="palette-card${selected ? ' selected' : ''}"
      data-palette-id="${escapeHtmlAttribute(palette.id)}"
      aria-pressed="${selected ? 'true' : 'false'}"
      onclick="previewPalette('${escapeHtmlAttribute(palette.id)}')">
      <span class="palette-card-swatches" aria-hidden="true">
        ${paletteSwatchesMarkup(palette.id)}
      </span>
      <span class="palette-card-copy">
        <strong>${escapeHtml(palette.name)}</strong>
        <span>${escapeHtml(palette.sourceName)}</span>
        <small>${escapeHtml(palette.mood)}</small>
      </span>
      <span class="palette-card-check" aria-hidden="true">✓</span>
    </button>`;
  }).join('');

  const status = $('palette-preview-status');
  if (!status) return;
  const isApplied = previewPaletteId === appliedPaletteId;
  status.textContent = isApplied
    ? `${paletteDisplayName(appliedPaletteId)}을 사용 중입니다.`
    : `${paletteDisplayName(previewPaletteId)} 미리보기 중 · 적용 전에는 저장되지 않습니다.`;
}

function previewPalette(paletteId) {
  previewPaletteId = setDocumentPalette(paletteId);
  renderPalettePicker();
}

function setPaletteCategory(category) {
  const allowedCategories = new Set(['all', 'soft', 'earth', 'vivid']);
  activePaletteCategory = allowedCategories.has(category) ? category : 'all';
  renderPalettePicker();
}

function openPalettePicker() {
  const overlay = $('palette-overlay');
  if (!overlay) return;
  paletteReturnFocus = document.activeElement;
  previewPaletteId = appliedPaletteId;
  activePaletteCategory = 'all';
  setDocumentPalette(appliedPaletteId);
  renderPalettePicker();
  overlay.classList.add('active');
  document.body.classList.add('palette-picker-open');
  setTimeout(() => {
    const target = overlay.querySelector(`[data-palette-id="${previewPaletteId}"]`)
      || overlay.querySelector('[data-palette-id]');
    target?.focus();
  }, 0);
}

function closePalettePicker() {
  $('palette-overlay')?.classList.remove('active');
  document.body.classList.remove('palette-picker-open');
  if (paletteReturnFocus && typeof paletteReturnFocus.focus === 'function') {
    paletteReturnFocus.focus();
  }
  paletteReturnFocus = null;
}

function cancelPalettePreview() {
  previewPaletteId = appliedPaletteId;
  setDocumentPalette(appliedPaletteId);
  closePalettePicker();
}

function applyPalettePreview() {
  appliedPaletteId = setDocumentPalette(previewPaletteId);
  const persisted = persistPaletteId(appliedPaletteId, window.localStorage);
  renderPaletteTrigger();
  closePalettePicker();
  notify(
    '색 조합 적용',
    persisted
      ? `${paletteDisplayName(appliedPaletteId)} 조합을 저장했습니다.`
      : `${paletteDisplayName(appliedPaletteId)} 조합을 적용했지만 브라우저에 저장하지 못했습니다.`,
    persisted ? 'ok' : 'err',
  );
}

function resetPalette() {
  appliedPaletteId = DEFAULT_PALETTE_ID;
  previewPaletteId = DEFAULT_PALETTE_ID;
  setDocumentPalette(DEFAULT_PALETTE_ID);
  persistPaletteId(DEFAULT_PALETTE_ID, window.localStorage);
  renderPaletteTrigger();
  closePalettePicker();
  notify('색 조합 초기화', 'Studio 기본 조합으로 돌아왔습니다.', 'ok');
}

function handlePaletteKeydown(event) {
  if (event.key !== 'Escape' || !$('palette-overlay')?.classList.contains('active')) return;
  event.preventDefault();
  cancelPalettePreview();
}

function initializePalette() {
  appliedPaletteId = storedPaletteId(window.localStorage);
  previewPaletteId = appliedPaletteId;
  setDocumentPalette(appliedPaletteId);
  renderPaletteTrigger();
  document.addEventListener('keydown', handlePaletteKeydown);
}
