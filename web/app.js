/* yt-w operator console boot. */

/* ── notif ─────────────────────────────────────────────────────────── */
let notifTimer = null;
function notify(title, msg, kind = 'info') {
  const n = $('notif');
  n.className = `notif active ${kind}`;
  $('notif-title').textContent = title;
  $('notif-msg').textContent = msg;
  if (notifTimer) clearTimeout(notifTimer);
  notifTimer = setTimeout(() => n.classList.remove('active'), 3500);
}

/* ── boot ──────────────────────────────────────────────────────────── */
initializePalette();
systemRefresh();
checkCookie();
loadChannels();
setDefaultMergeOutputName();
restoreMergeDownloadDirectory();
handleYouTubeOAuthCallback();
switchTab(state.activeTab);
setInterval(systemRefresh, 5000);
setInterval(checkCookie, 60000);
setInterval(() => { if (state.activeTab === 'merge') loadJobs(); }, 3000);
setInterval(() => { if (state.activeTab === 'split') loadSplitJobs(); }, 3000);
setInterval(() => { if (state.activeTab === 'youtube-upload') loadYouTubeUploadJobs(); }, 3000);
