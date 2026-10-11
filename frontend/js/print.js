/* Calendar download and the printable action plan. */
import { $, esc, fmtINR } from './util.js';
import { t } from './i18n.js';
import { auth } from './api.js';
import { state, eligibleMatches, readiness, hasDoc } from './state.js';
import { toast } from './ui.js';

export async function downloadCalendar() {
  if (!state.profileId) return;
  const headers = {};
  if (auth.token) headers.Authorization = `Bearer ${auth.token}`;
  if (auth.profileKey) headers['X-Profile-Key'] = auth.profileKey;
  try {
    const r = await fetch(`/api/agent/calendar/${state.profileId}`, { headers });
    if (!r.ok) throw new Error(r.statusText);
    const url = URL.createObjectURL(await r.blob());
    const a = Object.assign(document.createElement('a'), { href: url, download: 'lifepilot-deadlines.ics' });
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
    toast(t('home.calendar', 'Add to calendar') + ' ✓');
  } catch (err) {
    toast(err.message, 'bad');
  }
}

export function printPlan() {
  if (!state.run) return;
  const ins = state.run.insights;
  const r = readiness();
  const scheme = (m) => `
    <div class="p-scheme">
      <strong>${esc(m.title)}</strong> · ${esc(m.amount || '')}<br />
      <span class="p-muted">${esc(m.provider || '')} · ${esc(m.deadline || m.deadline_note || '')} · ${esc(m.url || '')}</span>
      ${(m.roadmap || []).length ? `<ol>${m.roadmap.map((s) => `<li>${esc(s)}</li>`).join('')}</ol>` : ''}
    </div>`;
  $('#printArea').innerHTML = `
    <h1>LifePilot action plan</h1>
    <p class="p-muted">${esc(state.profile?.name || '')} · ${new Date().toLocaleDateString('en-IN')}</p>
    <p>${ins.eligible_count} schemes you qualify for · ${esc(fmtINR(ins.estimated_annual_benefit))} a year · ${r.owned} of ${r.total} documents ready</p>
    <h2>Schemes to apply for</h2>
    ${eligibleMatches().map(scheme).join('') || '<p class="p-muted">None yet.</p>'}
    <h2>Documents</h2>
    <ul>${r.docs.map((d) => `<li>${hasDoc(d.document) ? '[x]' : '[ ]'} ${esc(d.document)} (needed by ${d.used_by})</li>`).join('')}</ul>`;
  window.print();
}
