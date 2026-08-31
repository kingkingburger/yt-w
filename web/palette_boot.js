(() => {
  const storageKey = 'yt-w.palette.v1';
  const paletteIds = new Set([
    'sage-blush',
    'ivory-sky',
    'orange-teal',
    'rose-mint',
    'coffee-olive',
    'magenta-blue',
    'lime-purple',
    'pale-yellow-dark-olive',
    'amber-coffee',
    'apricot-blue',
    'ochre-lavender',
    'terracotta-dusty-rose',
    'pine-navy',
    'jade-lavender',
    'red-black-green',
    'coral-midnight',
  ]);
  try {
    const paletteId = window.localStorage.getItem(storageKey);
    if (paletteIds.has(paletteId)) document.documentElement.dataset.palette = paletteId;
  } catch (_error) {
    // Storage can be unavailable in hardened browsers. The default theme remains usable.
  }
})();
