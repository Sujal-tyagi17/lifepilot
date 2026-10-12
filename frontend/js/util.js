/* Small shared helpers. No framework, no build step. */
export const $ = (s, r = document) => r.querySelector(s);
export const $$ = (s, r = document) => [...r.querySelectorAll(s)];

export const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

/** ₹ with Indian digit grouping: 1500000 -> ₹15,00,000 */
export const fmtINR = (n) => '₹' + Math.round(n || 0).toLocaleString('en-IN');

export function daysLeft(iso) {
  if (!iso) return null;
  const d = new Date(iso + 'T00:00:00');
  if (Number.isNaN(d.getTime())) return null;
  const today = new Date(); today.setHours(0, 0, 0, 0);
  return Math.round((d - today) / 86400000);
}

export function fmtDate(iso, lang = 'en') {
  if (!iso) return '';
  const d = new Date(iso + 'T00:00:00');
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(`${lang || 'en'}-IN`, { day: 'numeric', month: 'short', year: 'numeric' });
}

/** Annual rupee value of a recurring benefit; 0 for one-time or unknown amounts.
 *  Mirrors backend/app/services/analytics.py parse_amount ("₹20 lakh" = 20,00,000). */
export function parseAmount(text) {
  if (!text) return 0;
  const nums = [...text.matchAll(/₹\s*([\d,]+(?:\.\d+)?)\s*(lakhs?|lacs?|crores?|cr\b|l\b)?/gi)].map((m) => {
    let n = +m[1].replace(/,/g, '');
    const unit = (m[2] || '').toLowerCase();
    if (/^(lakh|lac|l$)/.test(unit)) n *= 1e5;
    else if (/^(crore|cr)/.test(unit)) n *= 1e7;
    return n;
  });
  if (!nums.length) return 0;
  const v = Math.max(...nums);
  if (/month/i.test(text)) return v * 12;
  if (/year|annum|p\.a/i.test(text)) return v;
  return 0;
}

/** eligible | partial | needs_review | closed (older saved runs only have `eligible`) */
export const matchStatus = (m) => m.status || (m.eligible ? 'eligible' : 'partial');

/** localStorage that never throws (private windows, blocked storage). */
export const store = {
  get(key, fallback = null) {
    try { const v = localStorage.getItem(key); return v === null ? fallback : JSON.parse(v); } catch { return fallback; }
  },
  set(key, value) { try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* ignore */ } },
  /** Plain strings (auth token, profile key, theme): stored as-is, as before. */
  raw(key) { try { return localStorage.getItem(key); } catch { return null; } },
  setRaw(key, value) { try { value == null ? localStorage.removeItem(key) : localStorage.setItem(key, String(value)); } catch { /* ignore */ } },
  remove(...keys) { try { keys.forEach((k) => localStorage.removeItem(k)); } catch { /* ignore */ } },
};

export function debounce(fn, ms) {
  let t;
  return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}

export const plural = (n, one, many) => (n === 1 ? one : many);
