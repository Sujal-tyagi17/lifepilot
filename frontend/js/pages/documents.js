/* Documents: one register of every document your schemes need. Files stay in this browser. */
import { esc } from '../util.js';
import { t } from '../i18n.js';
import { icon, toast, confirmDialog } from '../ui.js';
import { emptyCard, ring, animateIn } from '../components.js';
import { state, setState, readiness, hasDoc, saveDocs } from '../state.js';
import { vaultPut, vaultGet, vaultDelete, vaultClear } from '../vault.js';

const MAX_BYTES = 8 * 1024 * 1024;

function row(d) {
  const key = d.document.toLowerCase().trim();
  const file = state.vault[key];
  const have = hasDoc(d.document);
  const id = `doc-${btoa(unescape(encodeURIComponent(key))).replace(/[^a-z0-9]/gi, '').slice(0, 24)}`;
  return `<tr>
    <td><p class="doc-name">${esc(d.document)}</p></td>
    <td class="small quiet" title="${esc((d.schemes || []).join(', '))}">${esc(d.used_by === 1 ? t('docs.usedByOne', '1 scheme') : t('docs.usedBy', '{n} schemes', { n: d.used_by }))}</td>
    <td>
      <label class="check" for="${id}"><input type="checkbox" id="${id}" data-have="${esc(key)}" ${have ? 'checked' : ''} ${file ? 'disabled' : ''} />
        ${have ? `<span class="stamp stamp-have">${esc(t('st.have', 'Have'))}</span>` : `<span class="quiet small">${esc(t('docs.iHave', 'I have this'))}</span>`}</label>
    </td>
    <td>
      ${file ? `<div class="file-note">${icon('lock', 'icon-sm')}<span>${esc(file.name)} · ${Math.max(1, Math.round(file.size / 1024))} KB</span></div>
        <div class="row" style="gap:4px;margin-top:4px">
          <button class="btn btn-quiet btn-sm" type="button" data-open="${esc(key)}">${esc(t('btn.open', 'Open'))}</button>
          <button class="btn btn-quiet btn-sm" type="button" data-remove="${esc(key)}">${esc(t('docs.remove', 'Remove'))}</button>
        </div>`
        : `<label class="btn btn-secondary btn-sm">${icon('paperclip', 'icon-sm')}${esc(t('docs.attach', 'Attach file'))}
            <input type="file" class="sr-only" data-upload="${esc(key)}" accept=".pdf,.png,.jpg,.jpeg,.webp" /></label>`}
    </td>
  </tr>`;
}

const table = (docs) => `<table class="register">
  <thead><tr>
    <th scope="col">${esc(t('docs.th.doc', 'Document'))}</th><th scope="col">${esc(t('docs.th.used', 'Needed by'))}</th>
    <th scope="col">${esc(t('docs.th.status', 'Status'))}</th><th scope="col">${esc(t('docs.th.file', 'File'))}</th>
  </tr></thead>
  <tbody>${docs.map(row).join('')}</tbody></table>`;

export const documents = {
  title: () => t('nav.documents', 'Documents'),
  sub: () => t('docs.lede', 'Every document your schemes ask for, in one list. Mark what you have, or keep a copy in this browser.'),
  deps: ['run', 'vault', 'ownedDocs'],
  render(el) {
    if (!state.run) {
      el.innerHTML = emptyCard({ iconName: 'folder-check', title: t('docs.empty', 'Fill in your profile first to build your document list.'), action: `<a class="btn btn-primary" href="#/start">${esc(t('land.start', 'Get started free'))}</a>` });
      return;
    }
    const r = readiness();
    const mainKeys = new Set(r.docs.map((d) => d.document.toLowerCase().trim()));
    const others = (state.run.insights?.master_documents || []).filter((d) => !mainKeys.has(d.document.toLowerCase().trim()));

    el.innerHTML = `
      <section class="card docs-top">
        ${ring(r.pct, { size: 120, stroke: 10, label: `${r.pct}%` })}
        <div class="stack" style="margin-top:0">
          <p class="h1 num">${esc(t('home.readyOf', '{have} of {n} documents ready', { have: r.owned, n: r.total }))}</p>
          <p class="notice" style="margin-top:12px">${icon('shield-check')}<span>${esc(t('docs.privacy', 'Files stay in this browser and are never uploaded. They will not appear on another device.'))}</span></p>
        </div>
      </section>
      <section class="card section">${r.total ? table(r.docs) : `<p class="quiet" style="padding:22px">${esc(t('docs.none', 'No documents needed yet.'))}</p>`}</section>
      ${others.length ? `<details class="section"><summary class="h3" style="cursor:pointer">${esc(t('docs.others', 'For schemes you are close to'))} <span class="quiet num">(${others.length})</span></summary>
        <section class="card" style="margin-top:12px">${table(others)}</section></details>` : ''}
      ${Object.keys(state.vault).length ? `<div class="section"><button class="btn btn-danger-quiet" type="button" id="dClear">${icon('trash-2')}${esc(t('docs.clear', 'Remove all files'))}</button></div>` : ''}`;
    animateIn(el);

    el.querySelectorAll('[data-have]').forEach((cb) => cb.addEventListener('change', () => {
      cb.checked ? state.ownedDocs.add(cb.dataset.have) : state.ownedDocs.delete(cb.dataset.have);
      saveDocs();
      setState({ ownedDocs: state.ownedDocs });
    }));
    el.querySelectorAll('[data-upload]').forEach((inp) => inp.addEventListener('change', async () => {
      const f = inp.files[0]; if (!f) return;
      if (f.size > MAX_BYTES) { toast(t('docs.tooBig', 'File is larger than 8 MB'), 'bad'); return; }
      try {
        await vaultPut(inp.dataset.upload, f);
        state.ownedDocs.add(inp.dataset.upload); saveDocs();
        setState({ vault: { ...state.vault, [inp.dataset.upload]: { name: f.name, size: f.size } } });
        toast(t('docs.stored', 'File kept on this device'));
      } catch { toast('Could not store the file in this browser', 'bad'); }
    }));
    el.querySelectorAll('[data-open]').forEach((b) => b.addEventListener('click', async () => {
      const rec = await vaultGet(b.dataset.open); if (!rec) return;
      const url = URL.createObjectURL(rec.blob);
      window.open(url, '_blank', 'noopener');
      setTimeout(() => URL.revokeObjectURL(url), 30000);
    }));
    el.querySelectorAll('[data-remove]').forEach((b) => b.addEventListener('click', async () => {
      await vaultDelete(b.dataset.remove);
      const vault = { ...state.vault }; delete vault[b.dataset.remove];
      setState({ vault });
    }));
    el.querySelector('#dClear')?.addEventListener('click', async () => {
      const ok = await confirmDialog({ title: t('docs.clear', 'Remove all files'), body: t('docs.clearBody', 'This deletes every file you kept in this browser. Your checklist ticks stay.'), confirm: t('docs.clear', 'Remove all files'), danger: true });
      if (!ok) return;
      await vaultClear();
      setState({ vault: {} });
    });
  },
};
