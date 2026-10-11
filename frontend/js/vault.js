/* Local document vault in IndexedDB. Files never leave this browser. */
const DB = 'lifepilot-vault', STORE = 'files';

function open() {
  return new Promise((res, rej) => {
    const r = indexedDB.open(DB, 1);
    r.onupgradeneeded = () => r.result.createObjectStore(STORE);
    r.onsuccess = () => res(r.result);
    r.onerror = () => rej(r.error);
  });
}

function tx(mode, fn) {
  return open().then((db) => new Promise((res, rej) => {
    const t = db.transaction(STORE, mode);
    const out = fn(t.objectStore(STORE));
    t.oncomplete = () => res(out && out.result !== undefined ? out.result : out);
    t.onerror = () => rej(t.error);
  }));
}

export const vaultPut = (key, file) =>
  tx('readwrite', (s) => s.put({ name: file.name, type: file.type, size: file.size, blob: file, addedAt: Date.now() }, key));

export function vaultGet(key) {
  return open().then((db) => new Promise((res) => {
    const rq = db.transaction(STORE).objectStore(STORE).get(key);
    rq.onsuccess = () => res(rq.result || null);
    rq.onerror = () => res(null);
  }));
}

export function vaultList() {
  return open().then((db) => new Promise((res) => {
    const out = {};
    const rq = db.transaction(STORE).objectStore(STORE).openCursor();
    rq.onsuccess = () => {
      const c = rq.result;
      if (c) { out[c.key] = { name: c.value.name, size: c.value.size }; c.continue(); } else res(out);
    };
    rq.onerror = () => res(out);
  })).catch(() => ({}));
}

export const vaultDelete = (key) => tx('readwrite', (s) => s.delete(key));
export const vaultClear = () => tx('readwrite', (s) => s.clear());
