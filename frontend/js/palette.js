/* Command palette (Ctrl/⌘ K). */
import { $, esc } from './util.js';
import { t } from './i18n.js';
import { icon } from './ui.js';

let commands = [];
let items = [];
let idx = 0;

export function setCommands(list) { commands = list; }

function draw(q) {
  q = q.toLowerCase();
  items = commands.filter((c) => !q || `${c.label} ${c.keys || ''}`.toLowerCase().includes(q));
  idx = 0;
  $('#paletteList').innerHTML = items.length
    ? items.map((c, i) => `<li class="palette-item" role="option" id="pal-${i}" aria-selected="${i === 0}" data-i="${i}">${icon(c.icon)}<span>${esc(c.label)}</span></li>`).join('')
    : `<li class="palette-item quiet">${esc(t('palette.none', 'No matching command'))}</li>`;
  $('#paletteInput').setAttribute('aria-activedescendant', items.length ? 'pal-0' : '');
  $('#paletteList').querySelectorAll('[data-i]').forEach((li) => li.addEventListener('click', () => run(+li.dataset.i)));
}

function highlight() {
  $('#paletteList').querySelectorAll('[data-i]').forEach((li) => li.setAttribute('aria-selected', String(+li.dataset.i === idx)));
  $('#paletteInput').setAttribute('aria-activedescendant', `pal-${idx}`);
  $(`#pal-${idx}`)?.scrollIntoView({ block: 'nearest' });
}

function run(i) { const c = items[i]; $('#palette').close(); c?.run(); }

export function openPalette() {
  const dlg = $('#palette');
  dlg.innerHTML = `
    <label class="sr-only" for="paletteInput">${esc(t('palette.placeholder', 'Search commands and pages'))}</label>
    <input class="input" id="paletteInput" role="combobox" aria-expanded="true" aria-controls="paletteList" autocomplete="off" placeholder="${esc(t('palette.placeholder', 'Search commands and pages'))}" />
    <ul class="palette-list" id="paletteList" role="listbox"></ul>`;
  dlg.showModal();
  const input = $('#paletteInput');
  draw('');
  input.addEventListener('input', () => draw(input.value));
  input.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); idx = Math.min(idx + 1, items.length - 1); highlight(); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); idx = Math.max(idx - 1, 0); highlight(); }
    else if (e.key === 'Enter') { e.preventDefault(); run(idx); }
  });
  dlg.addEventListener('click', (e) => { if (e.target === dlg) dlg.close(); });
}

export function initPalette() {
  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      $('#palette').open ? $('#palette').close() : openPalette();
    }
  });
}
