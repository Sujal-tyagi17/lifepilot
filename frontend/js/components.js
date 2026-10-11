/* Reusable form controls and motion helpers. All controls are real form
   elements (radios, checkboxes, inputs), so FormData, keyboard use and
   screen readers work without extra code. */
import { esc, fmtINR } from './util.js';
import { icon } from './icons.js';
import { miniRosette } from './brand.js';

const reduceMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/** Pill chips. options: [[value, label, iconName?], ...]. type 'radio' or 'checkbox'. */
export function chips(name, options, current, { type = 'radio', label = '', id = name } = {}) {
  const sel = new Set([].concat(current ?? []).map(String));
  return `<fieldset class="field" id="${esc(id)}">
    ${label ? `<legend class="label" style="margin-bottom:8px">${esc(label)}</legend>` : ''}
    <div class="chips">${options.map(([v, l, ic]) => `
      <label class="chip"><input type="${type}" name="${esc(name)}" value="${esc(v)}" ${sel.has(String(v)) ? 'checked' : ''} />
        <span>${ic ? icon(ic, 'icon-sm') : ''}${esc(l)}</span></label>`).join('')}</div>
  </fieldset>`;
}

/** Big choice cards with an icon and a short description. */
export function choiceCards(name, options, current, { label = '' } = {}) {
  return `<fieldset class="field">
    ${label ? `<legend class="label" style="margin-bottom:8px">${esc(label)}</legend>` : ''}
    <div class="choice-grid">${options.map(([v, l, ic, sub]) => `
      <label class="choice"><input type="radio" name="${esc(name)}" value="${esc(v)}" ${String(current ?? '') === String(v) ? 'checked' : ''} />
        <span>${icon(ic || 'circle-dashed')}<span>${esc(l)}${sub ? `<br /><small>${esc(sub)}</small>` : ''}</span></span></label>`).join('')}</div>
  </fieldset>`;
}

/** Income slider with a live ₹ value and preset limits that schemes commonly use. */
export function incomeSlider(name, value, { label, hint, max = 1500000, presets = [100000, 250000, 450000, 800000] } = {}) {
  const v = Math.min(Number(value ?? 300000) || 0, max);
  return `<div class="field">
    <label class="label" for="f-${name}">${esc(label)}</label>
    <div class="slider" data-slider>
      <div class="slider-top"><output class="slider-value num" for="f-${name}">${esc(fmtINR(v))}</output><span class="tiny quiet">${esc(hint || '')}</span></div>
      <input class="range" type="range" id="f-${name}" name="${name}" min="0" max="${max}" step="10000" value="${v}" style="--pct:${(v / max) * 100}%" />
      <div class="presets">${presets.map((p) => `<button type="button" class="preset" data-preset="${p}">≤ ${esc(fmtINR(p))}</button>`).join('')}</div>
    </div>
  </div>`;
}

/** Search-as-you-type over a fixed list (native datalist). */
export function typeahead(name, list, value, { label, placeholder = '' } = {}) {
  return `<div class="field">
    <label class="label" for="f-${name}">${esc(label)}</label>
    <div class="input-icon">${icon('map-pin')}
      <input class="input" id="f-${name}" name="${name}" list="dl-${name}" value="${esc(value ?? '')}" placeholder="${esc(placeholder)}" autocomplete="off" />
    </div>
    <datalist id="dl-${name}">${list.map((s) => `<option value="${esc(s)}"></option>`).join('')}</datalist>
  </div>`;
}

export function switchRow(name, label, checked) {
  return `<label class="switch"><span>${esc(label)}</span><input type="checkbox" role="switch" name="${name}" ${checked ? 'checked' : ''} /></label>`;
}

/** Tag input. Writes comma-separated values to a hidden input named `name`. */
export function tagInput(name, values, { label, placeholder = '', suggestions = [] } = {}) {
  return `<div class="field" data-tags="${esc(name)}">
    <label class="label" for="t-${name}">${esc(label)}</label>
    <div class="tags" data-tagbox>
      ${values.map(tagChip).join('')}
      <input id="t-${name}" placeholder="${esc(placeholder)}" autocomplete="off" />
    </div>
    <input type="hidden" name="${esc(name)}" value="${esc(values.join(', '))}" />
    ${suggestions.length ? `<div class="suggest">${suggestions.map((s) => `<button type="button" data-add="${esc(s)}">+ ${esc(s)}</button>`).join('')}</div>` : ''}
  </div>`;
}
const tagChip = (v) => `<span class="tag" data-tag="${esc(v)}">${esc(v)}<button type="button" aria-label="Remove ${esc(v)}">${icon('x', 'icon-sm')}</button></span>`;

/** Wire up every slider and tag input inside `root`. Call after rendering. */
export function bindControls(root) {
  root.querySelectorAll('[data-slider]').forEach((box) => {
    const range = box.querySelector('input[type=range]');
    const out = box.querySelector('output');
    const sync = () => { out.textContent = fmtINR(+range.value); range.style.setProperty('--pct', `${(range.value / range.max) * 100}%`); };
    range.addEventListener('input', sync);
    box.querySelectorAll('[data-preset]').forEach((b) => b.addEventListener('click', () => {
      range.value = b.dataset.preset; sync(); range.dispatchEvent(new Event('input', { bubbles: true }));
    }));
  });

  root.querySelectorAll('[data-tags]').forEach((wrap) => {
    const box = wrap.querySelector('[data-tagbox]');
    const input = box.querySelector('input');
    const hidden = wrap.querySelector('input[type=hidden]');
    const values = () => [...box.querySelectorAll('[data-tag]')].map((t) => t.dataset.tag);
    const sync = () => { hidden.value = values().join(', '); hidden.dispatchEvent(new Event('input', { bubbles: true })); };
    const add = (raw) => {
      raw.split(',').map((s) => s.trim()).filter(Boolean).forEach((v) => {
        if (values().some((x) => x.toLowerCase() === v.toLowerCase())) return;
        input.insertAdjacentHTML('beforebegin', tagChip(v));
      });
      input.value = ''; sync();
      const have = new Set(values().map((x) => x.toLowerCase()));
      wrap.querySelectorAll('[data-add]').forEach((b) => { if (have.has(b.dataset.add.toLowerCase())) b.remove(); });
    };
    box.addEventListener('click', (e) => {
      const rm = e.target.closest('.tag button');
      if (rm) { rm.parentElement.remove(); sync(); input.focus(); return; }
      input.focus();
    });
    input.addEventListener('keydown', (e) => {
      if ((e.key === 'Enter' || e.key === ',') && input.value.trim()) { e.preventDefault(); add(input.value); }
      else if (e.key === 'Backspace' && !input.value) { const last = box.querySelector('[data-tag]:last-of-type'); if (last) { last.remove(); sync(); } }
    });
    input.addEventListener('blur', () => { if (input.value.trim()) add(input.value); });
    wrap.querySelectorAll('[data-add]').forEach((b) => b.addEventListener('click', () => { add(b.dataset.add); b.remove(); }));
  });
}

/** Animate a number from 0 to `to`. */
export function countUp(el, to, fmt = (n) => Math.round(n).toLocaleString('en-IN')) {
  if (!el) return;
  if (reduceMotion() || !to) { el.textContent = fmt(to); return; }
  const t0 = performance.now(), dur = 1100;
  const step = (t) => {
    const p = Math.min((t - t0) / dur, 1);
    el.textContent = fmt(to * (1 - Math.pow(1 - p, 3)));
    if (p < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

/** Circular progress ring markup. `pct` 0–100. */
export function ring(pct, { size = 112, stroke = 10, color = 'var(--green)', label = `${pct}%`, cls = 'ring' } = {}) {
  const r = (size - stroke) / 2, c = 2 * Math.PI * r;
  return `<div class="${cls}" style="width:${size}px;height:${size}px" role="img" aria-label="${esc(label)}">
    <svg viewBox="0 0 ${size} ${size}"><circle class="track" cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none" stroke-width="${stroke}" />
      <circle class="val" cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none" stroke-width="${stroke}" stroke="${color}"
        stroke-dasharray="${c}" stroke-dashoffset="${c}" data-offset="${c * (1 - pct / 100)}" /></svg>
    ${cls === 'ring' ? `<span class="ring-label num">${esc(label)}</span>` : `<b class="num">${esc(label)}</b>`}
  </div>`;
}

/** Start ring and bar animations after the elements are in the page. */
export function animateIn(root) {
  requestAnimationFrame(() => requestAnimationFrame(() => {
    root.querySelectorAll('circle[data-offset]').forEach((c) => { c.style.strokeDashoffset = c.dataset.offset; });
    root.querySelectorAll('[data-width]').forEach((s) => { s.style.width = s.dataset.width; });
  }));
  root.querySelectorAll('[data-count]').forEach((el) => {
    const money = el.dataset.money === '1';
    countUp(el, Number(el.dataset.count), money ? (n) => fmtINR(n) : undefined);
  });
}

/** Fade sections in as they scroll into view. */
export function reveal(root) {
  const items = root.querySelectorAll('.reveal');
  if (reduceMotion() || !('IntersectionObserver' in window)) { items.forEach((i) => i.classList.add('in')); return; }
  const io = new IntersectionObserver((entries) => entries.forEach((e) => {
    if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); }
  }), { threshold: .12, rootMargin: '0px 0px -40px 0px' });
  items.forEach((i) => io.observe(i));
}

export function emptyCard({ title, body = '', action = '', iconName = 'sparkles' }) {
  return `<div class="card empty"><div class="empty-rosette">${miniRosette()}</div><span class="empty-icon">${icon(iconName, 'icon-lg')}</span>
    <h2 class="h2">${esc(title)}</h2>${body ? `<p class="quiet">${esc(body)}</p>` : ''}${action ? `<div class="row row-wrap" style="margin-top:8px">${action}</div>` : ''}</div>`;
}
