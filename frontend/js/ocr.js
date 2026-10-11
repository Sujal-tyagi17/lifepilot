/* Reads text from a photo of a document, inside this browser.
   Tesseract.js and its English + Hindi models are served from /static/vendor/ocr,
   so the image never leaves the device; only the text is sent to be checked. */
const BASE = '/static/vendor/ocr';
let loading = null;
let worker = null;

function loadScript(src) {
  return new Promise((resolve, reject) => {
    const s = document.createElement('script');
    s.src = src;
    s.onload = resolve;
    s.onerror = () => reject(new Error('Could not load the text reader'));
    document.head.appendChild(s);
  });
}

let progressFn = () => {};

async function getWorker() {
  if (worker) return worker;
  if (!loading) {
    loading = (async () => {
      if (!window.Tesseract) await loadScript(`${BASE}/tesseract.min.js`);
      worker = await window.Tesseract.createWorker(['eng', 'hin'], 1, {
        workerPath: `${BASE}/worker.min.js`,
        corePath: BASE,              // picks the SIMD build when the browser supports it
        langPath: `${BASE}/lang`,
        gzip: true,
        workerBlobURL: false,        // the CSP allows workers from this server only
        logger: (m) => progressFn(m),
      });
      return worker;
    })().catch((err) => { loading = null; throw err; });
  }
  return loading;
}

/** Text in the image. onProgress gets { status, progress 0–1 }. */
export async function readImage(file, onProgress = () => {}) {
  progressFn = onProgress;
  const w = await getWorker();
  const { data } = await w.recognize(file);
  return { text: (data.text || '').trim(), confidence: Math.round(data.confidence || 0) };
}

export const ocrSupported = () => typeof WebAssembly === 'object' && typeof Worker === 'function';
