import subprocess
from pathlib import Path

from .test_youtube_upload import require_node


def test_status_distinguishes_success_active_failure_and_unknown_history():
    source = Path("web/youtube_history.js").read_text(encoding="utf-8")
    script = """
const assert = require('node:assert/strict');
const state = { youtubeUploadHistory: null, youtubeUploadJobs: [] };
assert.equal(youtubeUploadFileStatus('a').label, '기록 확인 중');
state.youtubeUploadHistory = undefined;
assert.equal(youtubeUploadFileStatus('a').label, '기록 확인 불가');
state.youtubeUploadHistory = [];
assert.equal(youtubeUploadFileStatus('a').label, '미업로드');
state.youtubeUploadJobs = [{source: 'a', status: 'failed'}];
assert.equal(youtubeUploadFileStatus('a').label, '미업로드 · 실패');
state.youtubeUploadJobs[0].status = 'cancelled';
assert.equal(youtubeUploadFileStatus('a').label, '미업로드 · 취소');
state.youtubeUploadJobs[0].status = 'running';
assert.equal(youtubeUploadFileStatus('a').label, '업로드 중');
state.youtubeUploadJobs[0].status = 'failed';
state.youtubeUploadHistory = [{source: 'a', video_id: 'video'}];
assert.equal(youtubeUploadFileStatus('a').label, '업로드 완료');
assert.equal(youtubeUploadFileStatus('b').label, '미업로드');
const API = '';
let renders = 0;
function renderYouTubeUploadFileList() { renders++; }
global.fetch = async () => ({ok: true, json: async () => [{source: 'b'}]});
(async () => {
  await loadYouTubeUploadHistory();
  assert.equal(youtubeUploadFileStatus('b').label, '업로드 완료');
  global.fetch = async () => ({ok: false});
  await loadYouTubeUploadHistory();
  assert.equal(youtubeUploadFileStatus('b').label, '기록 확인 불가');
  assert.equal(renders, 2);
})().catch(error => { console.error(error); process.exitCode = 1; });
"""
    subprocess.run([require_node(), "-e", source + script], check=True)
