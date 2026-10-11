/* Toasts, confirm dialog and small rendering helpers. */
import { $, esc } from './util.js';
import { icon } from './icons.js';
import { t } from './i18n.js';

export { icon };

export function toast(message, kind = 'info') {
  const el = document.createElement('div');
  el.className = `toast ${kind === 'bad' ? 'bad' : ''}`;
  el.innerHTML = `${icon(kind === 'bad' ? 'triangle-alert' : 'check', 'icon-sm')}<span>${esc(message)}</span>`;
  $('#toasts').appendChild(el);
  setTimeout(() => el.remove(), kind === 'bad' ? 6000 : 3500);
}

/** Promise<boolean>. Uses the native <dialog>, so focus is trapped and Esc cancels. */
export function confirmDialog({ title, body, confirm, danger = false }) {
  const dlg = $('#dialog');
  dlg.innerHTML = `
    <form method="dialog">
      <div class="dialog-body stack">
        <h2 class="h2" id="dlgTitle">${esc(title)}</h2>
        <p class="quiet">${esc(body)}</p>
      </div>
      <div class="dialog-actions">
        <button class="btn btn-secondary" value="cancel">${esc(t('cancel', 'Cancel'))}</button>
        <button class="btn ${danger ? 'btn-danger' : 'btn-primary'}" value="ok">${esc(confirm)}</button>
      </div>
    </form>`;
  dlg.setAttribute('aria-labelledby', 'dlgTitle');
  return new Promise((resolve) => {
    dlg.addEventListener('close', () => resolve(dlg.returnValue === 'ok'), { once: true });
    dlg.showModal();
  });
}

const STAMP = {
  eligible: ['stamp-eligible', 'st.eligible', 'Eligible'],
  partial: ['stamp-partial', 'st.partial', 'Partial'],
  needs_review: ['stamp-review', 'st.review', 'Check portal'],
  closed: ['stamp-closed', 'st.closed', 'Closed'],
};
export function stamp(status, extra = '') {
  const [cls, key, en] = STAMP[status] || STAMP.partial;
  return `<span class="stamp ${cls} ${extra}">${esc(t(key, en))}</span>`;
}

export const skeleton = (lines = 4) =>
  `<div aria-hidden="true"><div class="skeleton sk-title"></div>${Array.from({ length: lines }, (_, i) =>
    `<div class="skeleton sk-line" style="width:${92 - i * 9}%"></div>`).join('')}</div>`;
