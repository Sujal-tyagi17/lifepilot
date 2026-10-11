/* LifePilot brand: the paper-plane mark and guilloché rosettes, the fine
   engraved line work printed on Indian certificates and banknotes. */

let uid = 0;

/** The logo mark: a paper plane folded from a document, on an ink tile. */
export function logoMark(cls = '') {
  const id = `lm${uid++}`;
  return `<svg class="logo-mark ${cls}" viewBox="0 0 64 64" aria-hidden="true" focusable="false">
    <defs>
      <linearGradient id="${id}t" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#1b2c78"/><stop offset="1" stop-color="#0b1640"/></linearGradient>
      <linearGradient id="${id}w" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stop-color="#ff6a00"/><stop offset="1" stop-color="#ffa53d"/></linearGradient>
      <linearGradient id="${id}f" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ffd36e"/><stop offset="1" stop-color="#ffb02e"/></linearGradient>
    </defs>
    <rect width="64" height="64" rx="16" fill="url(#${id}t)"/>
    <g class="lm-ring"><circle cx="32" cy="32" r="24" fill="none" stroke="#ffc14d" stroke-opacity=".3" stroke-width="1" stroke-dasharray="1.2 2.2"/></g>
    <circle cx="32" cy="32" r="19" fill="none" stroke="#fff" stroke-opacity=".12" stroke-width=".8"/>
    <g class="lm-plane">
      <path d="M11 33.5 L53 13 L30.5 38.5 Z" fill="url(#${id}w)"/>
      <path d="M30.5 38.5 L53 13 L41.5 51 Z" fill="url(#${id}f)"/>
      <path d="M30.5 38.5 L33 48 L37 43.2 Z" fill="#c24a00"/>
    </g>
    <g class="lm-trail"><circle cx="17" cy="47" r="1.9" fill="#ffc14d"/><circle cx="11" cy="52.5" r="1.4" fill="#ffc14d" fill-opacity=".6"/></g>
  </svg>`;
}

const gcd = (a, b) => (b ? gcd(b, a % b) : a);

/** One hypotrochoid curve (a spirograph line) as an SVG path, with its length. */
function curve(R, r, d, scale, steps = 1400) {
  const turns = r / gcd(R, r);
  const T = Math.PI * 2 * turns;
  let path = '', len = 0, px = 0, py = 0;
  for (let i = 0; i <= steps; i++) {
    const t = (T * i) / steps;
    const x = ((R - r) * Math.cos(t) + d * Math.cos(((R - r) / r) * t)) * scale;
    const y = ((R - r) * Math.sin(t) - d * Math.sin(((R - r) / r) * t)) * scale;
    path += `${i ? 'L' : 'M'}${x.toFixed(2)} ${y.toFixed(2)}`;
    if (i) len += Math.hypot(x - px, y - py);
    px = x; py = y;
  }
  return { d: path, len: Math.ceil(len) };
}

/** A woven band: copies of a wavy circle, each shifted a little, like engraved
    security print. r(t) = radius + amp · sin(lobes · t + phase). */
function band(radius, amp, lobes, copies, steps = 480) {
  const out = [];
  for (let k = 0; k < copies; k++) {
    const ph = (Math.PI * 2 * k) / copies;   // spread over a full wave, so the lines cross and weave
    let d = '', len = 0, px = 0, py = 0;
    for (let i = 0; i <= steps; i++) {
      const t = (Math.PI * 2 * i) / steps;
      const r = radius + amp * Math.sin(lobes * t + ph) + amp * 0.35 * Math.sin(lobes * 2 * t - ph);
      const x = r * Math.cos(t), y = r * Math.sin(t);
      d += `${i ? 'L' : 'M'}${x.toFixed(2)} ${y.toFixed(2)}`;
      if (i) len += Math.hypot(x - px, y - py);
      px = x; py = y;
    }
    out.push({ d, len: Math.ceil(len) });
  }
  return out;
}

// From outside in: a band, its colour variable, line width and opacity
const LAYERS = () => [
  [band(90, 6, 24, 8), '--ros-a', 0.35, 0.6],
  [band(72, 7, 18, 8), '--ros-b', 0.35, 0.55],
  [band(52, 7, 14, 7), '--ros-a', 0.35, 0.6],
  [band(32, 6, 10, 6), '--ros-c', 0.4, 0.7],
  [band(15, 3, 7, 5), '--ros-b', 0.4, 0.7],
];

/** A full rosette: engraved rings that draw themselves in and turn slowly.
    Each ring is its own layer so turning it is cheap for the browser. */
export function rosette({ cls = '', layers = LAYERS() } = {}) {
  const svg = (inner, i, extra = '') => `<svg class="ros-ring ${extra}" style="--i:${i}" viewBox="-102 -102 204 204" aria-hidden="true" focusable="false">${inner}</svg>`;
  return `<div class="rosette ${cls}" aria-hidden="true">
    ${svg('<circle r="99" fill="none" stroke="var(--ros-b)" stroke-width=".4" stroke-opacity=".5" stroke-dasharray="1 2.4" />', 0, 'ros-dots')}
    ${layers.map(([paths, col, w, op], i) => svg(paths.map((c) =>
      `<path d="${c.d}" fill="none" stroke="var(${col})" stroke-width="${w}" stroke-opacity="${op}" style="--len:${c.len}" />`).join(''), i + 1)).join('')}
    ${svg('<circle r="4" fill="var(--ros-c)" />', layers.length + 1, 'ros-core')}
  </div>`;
}

/** A small rosette for corners of cards. */
export const miniRosette = (cls = '') => rosette({ cls, layers: [[band(88, 7, 16, 6), '--ros-a', 0.6, 0.6], [band(62, 8, 12, 6), '--ros-b', 0.6, 0.55], [band(36, 6, 8, 5), '--ros-c', 0.7, 0.65]] });
