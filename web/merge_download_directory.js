const MERGE_DOWNLOAD_DB_NAME = 'yt-w-settings';
const MERGE_DOWNLOAD_DB_VERSION = 1;
const MERGE_DOWNLOAD_STORE_NAME = 'directory-handles';
const MERGE_DOWNLOAD_DIRECTORY_KEY = 'merge-download-directory';

function openMergeDownloadDatabase(indexedDBFactory) {
  return new Promise((resolve, reject) => {
    const request = indexedDBFactory.open(
      MERGE_DOWNLOAD_DB_NAME,
      MERGE_DOWNLOAD_DB_VERSION,
    );
    request.onupgradeneeded = () => {
      const database = request.result;
      if (!database.objectStoreNames.contains(MERGE_DOWNLOAD_STORE_NAME)) {
        database.createObjectStore(MERGE_DOWNLOAD_STORE_NAME);
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error || new Error('설정 저장소를 열 수 없습니다'));
  });
}

async function loadMergeDownloadDirectoryHandle(indexedDBFactory) {
  const database = await openMergeDownloadDatabase(indexedDBFactory);
  try {
    return await new Promise((resolve, reject) => {
      const transaction = database.transaction(MERGE_DOWNLOAD_STORE_NAME, 'readonly');
      const request = transaction
        .objectStore(MERGE_DOWNLOAD_STORE_NAME)
        .get(MERGE_DOWNLOAD_DIRECTORY_KEY);
      request.onsuccess = () => resolve(request.result || null);
      request.onerror = () => reject(request.error || new Error('저장 폴더를 불러올 수 없습니다'));
    });
  } finally {
    database.close();
  }
}

async function saveMergeDownloadDirectoryHandle(handle, indexedDBFactory) {
  const database = await openMergeDownloadDatabase(indexedDBFactory);
  try {
    await new Promise((resolve, reject) => {
      const transaction = database.transaction(MERGE_DOWNLOAD_STORE_NAME, 'readwrite');
      transaction.objectStore(MERGE_DOWNLOAD_STORE_NAME).put(
        handle,
        MERGE_DOWNLOAD_DIRECTORY_KEY,
      );
      transaction.oncomplete = () => resolve();
      transaction.onerror = () => reject(
        transaction.error || new Error('저장 폴더를 기억할 수 없습니다'),
      );
      transaction.onabort = transaction.onerror;
    });
  } finally {
    database.close();
  }
}

async function ensureMergeDownloadDirectoryPermission(handle) {
  const options = { mode: 'readwrite' };
  if (await handle.queryPermission(options) === 'granted') return true;
  return await handle.requestPermission(options) === 'granted';
}

function mergeDownloadFileName(output) {
  const normalized = String(output || '').replaceAll('\\', '/');
  return normalized.split('/').pop() || 'merged.mp4';
}

function numberedMergeDownloadFileName(filename, index) {
  if (index === 0) return filename;
  const extensionIndex = filename.lastIndexOf('.');
  if (extensionIndex <= 0) return `${filename} (${index})`;
  return `${filename.slice(0, extensionIndex)} (${index})${filename.slice(extensionIndex)}`;
}

async function createAvailableMergeDownloadFile(directoryHandle, filename) {
  for (let index = 0; index < 10000; index += 1) {
    const candidate = numberedMergeDownloadFileName(filename, index);
    try {
      await directoryHandle.getFileHandle(candidate);
    } catch (error) {
      if (error?.name !== 'NotFoundError') throw error;
      const handle = await directoryHandle.getFileHandle(candidate, { create: true });
      return { handle, name: candidate };
    }
  }
  throw new Error('사용 가능한 저장 파일명을 찾을 수 없습니다');
}

async function writeMergedFileToDirectory(
  downloadUrl,
  output,
  directoryHandle,
  fetcher = fetch,
) {
  const response = await fetcher(downloadUrl);
  if (!response.ok) throw new Error('병합 파일을 내려받을 수 없습니다');

  const destination = await createAvailableMergeDownloadFile(
    directoryHandle,
    mergeDownloadFileName(output),
  );
  const writable = await destination.handle.createWritable();
  if (response.body && typeof response.body.pipeTo === 'function') {
    await response.body.pipeTo(writable);
    return destination.name;
  }

  await writable.write(await response.blob());
  await writable.close();
  return destination.name;
}
