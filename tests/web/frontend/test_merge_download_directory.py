import json
import shutil
import subprocess
from pathlib import Path

import pytest


def require_node() -> str:
    node = shutil.which("node")
    if node is None:
        pytest.fail("node is required for frontend directory tests")
    return node


def read_directory_helpers() -> str:
    return Path("web/merge_download_directory.js").read_text(encoding="utf-8")


def run_node(script: str) -> dict:
    result = subprocess.run(
        [require_node(), "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_merge_page_exposes_saved_pc_directory_picker() -> None:
    index_html = Path("web/index.html").read_text(encoding="utf-8")
    app_js = Path("web/app.js").read_text(encoding="utf-8")

    assert 'id="merge-download-directory"' in index_html
    assert 'id="btn-merge-download-directory"' in index_html
    assert index_html.index("merge_download_directory.js") < index_html.index("app.js")
    assert "restoreMergeDownloadDirectory();" in app_js
    assert "saveMergedJob('${j.id}')" in app_js
    assert "window.isSecureContext" in app_js


def test_merge_directory_handle_round_trips_through_indexed_db() -> None:
    script = read_directory_helpers() + r"""
function makeIndexedDBFactory() {
  let saved = null;
  let closeCount = 0;
  const database = {
    transaction(_store, mode) {
      const transaction = { mode };
      transaction.objectStore = () => ({
        put(value, key) {
          saved = { value, key };
          setTimeout(() => transaction.oncomplete(), 0);
        },
        get(key) {
          const request = {};
          setTimeout(() => {
            request.result = saved?.key === key ? saved.value : null;
            request.onsuccess();
          }, 0);
          return request;
        },
      });
      return transaction;
    },
    close() { closeCount += 1; },
  };
  return {
    factory: {
      open() {
        const request = {};
        setTimeout(() => {
          request.result = database;
          request.onsuccess();
        }, 0);
        return request;
      },
    },
    result() { return { saved, closeCount }; },
  };
}

(async () => {
  const storage = makeIndexedDBFactory();
  const handle = { kind: 'directory', name: 'Videos' };
  await saveMergeDownloadDirectoryHandle(handle, storage.factory);
  const loaded = await loadMergeDownloadDirectoryHandle(storage.factory);
  console.log(JSON.stringify({
    loadedName: loaded.name,
    key: storage.result().saved.key,
    closeCount: storage.result().closeCount,
  }));
})();
"""

    assert run_node(script) == {
        "loadedName": "Videos",
        "key": "merge-download-directory",
        "closeCount": 2,
    }


def test_merged_file_streams_to_selected_directory() -> None:
    script = read_directory_helpers() + r"""
(async () => {
  const events = [];
  const writable = { marker: 'writable' };
  const directoryHandle = {
    async getFileHandle(name, options) {
      if (!options?.create) throw { name: 'NotFoundError' };
      events.push(['file', name, options.create]);
      return {
        async createWritable() {
          events.push(['createWritable']);
          return writable;
        },
      };
    },
  };
  const fetcher = async (url) => ({
    ok: true,
    body: {
      async pipeTo(target) {
        events.push(['pipeTo', target === writable]);
      },
    },
  });

  const savedFileName = await writeMergedFileToDirectory(
    '/api/merge/jobs/abc/download',
    'merged/2026-07-12.mp4',
    directoryHandle,
    fetcher,
  );
  console.log(JSON.stringify({ events, savedFileName }));
})();
"""

    assert run_node(script) == {
        "events": [
            ["file", "2026-07-12.mp4", True],
            ["createWritable"],
            ["pipeTo", True],
        ],
        "savedFileName": "2026-07-12.mp4",
    }


def test_existing_merge_download_is_not_overwritten() -> None:
    script = read_directory_helpers() + r"""
(async () => {
  const existing = new Set(['result.mp4', 'result (1).mp4']);
  const directoryHandle = {
    async getFileHandle(name, options) {
      if (!options?.create) {
        if (existing.has(name)) return { name };
        throw { name: 'NotFoundError' };
      }
      existing.add(name);
      return { name };
    },
  };
  const destination = await createAvailableMergeDownloadFile(
    directoryHandle,
    'result.mp4',
  );
  console.log(JSON.stringify({ name: destination.name, files: [...existing] }));
})();
"""

    assert run_node(script) == {
        "name": "result (2).mp4",
        "files": ["result.mp4", "result (1).mp4", "result (2).mp4"],
    }


def test_saved_directory_permission_can_be_restored() -> None:
    script = read_directory_helpers() + r"""
(async () => {
  const calls = [];
  const handle = {
    async queryPermission(options) {
      calls.push(['query', options.mode]);
      return 'prompt';
    },
    async requestPermission(options) {
      calls.push(['request', options.mode]);
      return 'granted';
    },
  };
  const granted = await ensureMergeDownloadDirectoryPermission(handle);
  console.log(JSON.stringify({ granted, calls }));
})();
"""

    assert run_node(script) == {
        "granted": True,
        "calls": [["query", "readwrite"], ["request", "readwrite"]],
    }
