/* Motion layer: magnetic buttons, a spotlight on ink panels, tilt, the stamp
   burst and the rosette following the pointer. One set of document listeners,
   so pages can re-render freely. Everything stops for "reduce motion". */

const reduce = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
const finePointer = () => matchMedia('(pointer: fine)').matches;

let raf = 0, last = null;

function onMove(e) {
  last = e;
  if (!raf) raf = requestAnimationFrame(frame);
}

function frame() {
  raf = 0;
  const e = last; if (!e) return;
  const target = e.target instanceof Element ? e.target : null;

  // Spotlight on ink panels: a soft light under the pointer
  const ink = target?.closest('.ink');
  if (ink) {
    const r = ink.getBoundingClientRect();
    ink.style.setProperty('--mx', `${e.clientX - r.left}px`);
    ink.style.setProperty('--my', `${e.clientY - r.top}px`);
  }

  // The rosette leans toward the pointer
  const hero = target?.closest('[data-parallax]');
  if (hero) {
    const r = hero.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width - 0.5, y = (e.clientY - r.top) / r.height - 0.5;
    hero.style.setProperty('--px', x.toFixed(3));
    hero.style.setProperty('--py', y.toFixed(3));
  }

  // Magnetic buttons pull a few pixels toward the pointer
  document.querySelectorAll('.magnetic.is-near').forEach((b) => { if (!b.contains(target)) { b.classList.remove('is-near'); b.style.transform = ''; } });
  const mag = target?.closest('.magnetic');
  if (mag) {
    const r = mag.getBoundingClientRect();
    const x = e.clientX - (r.left + r.width / 2), y = e.clientY - (r.top + r.height / 2);
    mag.classList.add('is-near');
    mag.style.transform = `translate(${x * 0.18}px, ${y * 0.28}px)`;
    mag.style.setProperty('--sx', `${((e.clientX - r.left) / r.width) * 100}%`);
  }

  // Cards with data-tilt turn slightly toward the pointer
  document.querySelectorAll('[data-tilt].is-tilting').forEach((c) => { if (!c.contains(target)) { c.classList.remove('is-tilting'); c.style.transform = ''; } });
  const tilt = target?.closest('[data-tilt]');
  if (tilt) {
    const r = tilt.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width - 0.5, y = (e.clientY - r.top) / r.height - 0.5;
    tilt.classList.add('is-tilting');
    tilt.style.transform = `perspective(1100px) rotateY(${x * 7}deg) rotateX(${-y * 7}deg) translateZ(0)`;
  }
}

/** A burst of saffron and marigold flecks from the middle of an element. */
export function burst(el, { count = 26, spread = 120 } = {}) {
  if (!el || reduce()) return;
  const r = el.getBoundingClientRect();
  const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
  const colours = ['#ff7a1a', '#ffc14d', '#ffa53d', '#0e8c7f', '#3d4fd8'];
  const layer = document.createElement('div');
  layer.className = 'burst';
  document.body.appendChild(layer);
  for (let i = 0; i < count; i++) {
    const p = document.createElement('i');
    const a = (Math.PI * 2 * i) / count + Math.random() * 0.4;
    const d = spread * (0.5 + Math.random() * 0.7);
    const size = 4 + Math.random() * 6;
    p.style.cssText = `left:${cx}px;top:${cy}px;width:${size}px;height:${size * (Math.random() > 0.5 ? 1 : 2.4)}px;background:${colours[i % colours.length]}`;
    layer.appendChild(p);
    p.animate([
      { transform: 'translate(-50%,-50%) rotate(0deg) scale(1)', opacity: 1 },
      { transform: `translate(calc(-50% + ${Math.cos(a) * d}px), calc(-50% + ${Math.sin(a) * d + 40}px)) rotate(${Math.random() * 540 - 270}deg) scale(.4)`, opacity: 0 },
    ], { duration: 900 + Math.random() * 500, easing: 'cubic-bezier(.15,.7,.3,1)', fill: 'forwards' });
  }
  setTimeout(() => layer.remove(), 1600);
}

/** Split a heading's words into spans that rise one after another. */
export function splitWords(el) {
  if (!el || el.dataset.split) return;
  el.dataset.split = '1';
  let i = 0;
  const walk = (node) => {
    [...node.childNodes].forEach((n) => {
      if (n.nodeType === 3) {
        const frag = document.createDocumentFragment();
        n.textContent.split(/(\s+)/).forEach((w) => {
          if (!w) return;
          if (/^\s+$/.test(w)) { frag.appendChild(document.createTextNode(w)); return; }
          const outer = document.createElement('span'); outer.className = 'w';
          const inner = document.createElement('span'); inner.textContent = w; inner.style.setProperty('--w', i++);
          outer.appendChild(inner); frag.appendChild(outer);
        });
        n.replaceWith(frag);
      } else if (n.nodeType === 1 && !n.classList.contains('sr-only') && !n.classList.contains('cycle')) {
        walk(n);
      } else if (n.nodeType === 1 && n.classList.contains('cycle')) {
        n.style.setProperty('--w', i++); n.classList.add('w-cycle');
      }
    });
  };
  walk(el);
}

export function initFx() {
  if (reduce() || !finePointer()) return;
  document.addEventListener('pointermove', onMove, { passive: true });
}
