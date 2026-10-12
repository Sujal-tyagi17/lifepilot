/* Documents: one register of every document your schemes need. Files stay in this browser. */
import { esc } from '../util.js';
import { t } from '../i18n.js';
import { icon, toast, confirmDialog } from '../ui.js';
import { emptyCard, ring, animateIn } from '../components.js';
import { state, setState, readiness, hasDoc, saveDocs } from '../state.js';
import { vaultPut, vaultGet, vaultDelete, vaultClear } from '../vault.js';
import { verifyDocument } from '../features.js';
import { readImage, ocrSupported } from '../ocr.js';

/* ── Document scanner: OCR in the browser, then the text is checked against the profile ── */
let lastScan = null;   // { result, file } kept while you stay on the page

function checkRow(c) {
  const ic = c.ok === true ? 'circle-check' : c.ok === false ? 'circle-x' : 'circle-help';
  return `<li class="${c.ok === true ? 'ok' : c.ok === false ? 'gap' : 'quiet'}">${icon(ic, 'icon-sm')}<span style="color:var(--ink)">${esc(c.message)}</span></li>`;
}

const FIELD_NAMES = {
  issue_date: ['scan.fDate', 'Issue date'], annual_income: ['scan.fIncome', 'Annual income'], percentage: ['scan.fPct', 'Percentage'],
  cgpa: ['scan.fCgpa', 'CGPA'], category: ['scan.fCat', 'Category'], disability_percent: ['scan.fDis', 'Disability'],
  aadhaar_last4: ['scan.fAadhaar', 'Aadhaar (last 4 digits)'], name_match: ['scan.fName', 'Name match'],
};

function fieldValue(k, v) {
  if (k === 'annual_income') return '₹' + Number(v).toLocaleString('en-IN');
  if (k === 'name_match') return `${Math.round(v * 100)}%`;
  if (k === 'percentage' || k === 'disability_percent') return `${v}%`;
  if (k === 'aadhaar_last4') return `XXXX XXXX ${v}`;
  return String(v);
}

function scanResult(res) {
  const c = res.classifier || {};
  const verdict = res.verdict === 'ok' ? ['stamp-eligible', t('scan.vOk', 'Looks consistent')]
    : res.verdict === 'check' ? ['stamp-closed', t('scan.vCheck', 'Check this')] : ['stamp-review', t('scan.vNone', 'Nothing to check')];
  const fields = Object.entries(res.fields || {});
  const docs = res.documents || [];
  return `<div class="scan-result">
    <div class="row" style="justify-content:space-between;gap:12px;align-items:flex-start">
      <div><p class="tiny quiet" style="font-weight:700;color:var(--saffron-deep)">${esc(t('scan.type', 'Document type'))}</p>
        <p class="h3">${esc(res.type_label)}</p>
        <p class="tiny quiet">${esc(c.by === 'model' ? t('scan.byModel', 'ML document classifier, {p}% sure', { p: Math.round((c.confidence || 0) * 100) }) : t('scan.byKeywords', 'recognised by keywords'))}</p></div>
      <span class="stamp ${verdict[0]}">${esc(verdict[1])}</span>
    </div>
    ${fields.length ? `<dl class="scan-fields">${fields.map(([k, v]) => `<div><dt>${esc(t(...(FIELD_NAMES[k] || [k, k])))}</dt><dd class="num">${esc(fieldValue(k, v))}</dd></div>`).join('')}</dl>` : ''}
    ${(res.checks || []).length ? `<ul class="facts-list">${res.checks.map(checkRow).join('')}</ul>` : `<p class="small quiet">${esc(t('scan.noChecks', 'No details could be checked. Try a sharper photo, or paste the text.'))}</p>`}
    <p class="notice tiny" style="margin-top:12px">${icon('info', 'icon-sm')}<span>${esc(t('scan.note', 'This checks that the document matches your profile and the scheme rules. It cannot tell whether a document is genuine.'))}</span></p>
    ${docs.length ? `<div class="row row-wrap" style="margin-top:12px;gap:8px">
      <button class="btn btn-primary btn-sm" type="button" id="scanAdd">${icon('check', 'icon-sm')}${esc(t('scan.add', 'Mark as I have: {doc}', { doc: docs[0] }))}</button>
      ${docs.length > 1 ? `<span class="tiny quiet">${esc(t('scan.addAlso', 'also ticks {n} other names for it', { n: docs.length - 1 }))}</span>` : ''}</div>` : ''}
    <details style="margin-top:10px"><summary class="tiny quiet" style="cursor:pointer">${esc(t('scan.preview', 'Text read (numbers hidden)'))}</summary><p class="tiny quiet scan-preview">${esc(res.preview)}</p></details>
  </div>`;
}

function scanner() {
  return `<section class="card panel-pad section" aria-labelledby="scanH">
    <div class="row" style="gap:12px;align-items:flex-start">
      <span class="insight-icon" style="background:var(--indigo);color:#fff">${icon('scan-line')}</span>
      <div style="flex:1;min-width:0">
        <h2 class="h3" id="scanH">${esc(t('scan.title', 'Scan a document'))}</h2>
        <p class="small quiet">${esc(t('scan.lede', 'Take a photo of a certificate. We read it in this browser, find what it is, and check it against your profile: name, income limit, date and category.'))}</p>
        <div class="row row-wrap" style="gap:8px;margin-top:12px">
          ${ocrSupported() ? `<label class="btn btn-secondary btn-sm">${icon('scan-line', 'icon-sm')}${esc(t('scan.pick', 'Photo or image'))}
            <input type="file" class="sr-only" id="scanFile" accept="image/*" capture="environment" /></label>` : ''}
          <button class="btn btn-quiet btn-sm" type="button" id="scanPasteBtn">${icon('file-pen', 'icon-sm')}${esc(t('scan.paste', 'Paste the text instead'))}</button>
        </div>
        <div id="scanPaste" hidden style="margin-top:10px">
          <label class="sr-only" for="scanText">${esc(t('scan.paste', 'Paste the text instead'))}</label>
          <textarea class="input" id="scanText" rows="4" maxlength="20000" placeholder="${esc(t('scan.pastePh', 'Text from the certificate'))}"></textarea>
          <button class="btn btn-primary btn-sm" type="button" id="scanCheck" style="margin-top:8px">${esc(t('scan.check', 'Check'))}</button>
        </div>
        <div id="scanStatus" aria-live="polite"></div>
        <div id="scanOut">${lastScan ? scanResult(lastScan.result) : ''}</div>
        <p class="tiny quiet" style="margin-top:10px">${icon('lock', 'icon-sm')} ${esc(t('scan.privacy', 'The image stays on this device. Only the text read from it is sent to be checked, and nothing is stored. PDFs: take a screenshot first.'))}</p>
      </div>
    </div>
  </section>`;
}

function bindScanner(el) {
  const status = el.querySelector('#scanStatus');
  const out = el.querySelector('#scanOut');
  const show = (result, file) => {
    lastScan = { result, file };
    out.innerHTML = scanResult(result);
    bindAdd();
  };
  const check = async (text, file) => {
    status.innerHTML = `<p class="working quiet small" style="margin-top:10px"><span class="spinner"></span>${esc(t('scan.checking', 'Checking…'))}</p>`;
    try { show(await verifyDocument(text), file); } catch (err) { toast(err.message, 'bad'); }
    status.innerHTML = '';
  };
  const bindAdd = () => el.querySelector('#scanAdd')?.addEventListener('click', async () => {
    const { result, file } = lastScan;
    const keys = (result.documents || []).map((d) => d.toLowerCase().trim());
    keys.forEach((k) => state.ownedDocs.add(k));
    saveDocs();
    let vault = state.vault;
    if (file && keys[0] && !state.vault[keys[0]] && file.size <= MAX_BYTES) {
      try { await vaultPut(keys[0], file); vault = { ...state.vault, [keys[0]]: { name: file.name, size: file.size } }; } catch { /* checklist tick is enough */ }
    }
    lastScan = null;
    toast(t('scan.added', 'Added to your documents'));
    setState({ ownedDocs: state.ownedDocs, vault });
  });
  bindAdd();
  el.querySelector('#scanPasteBtn').addEventListener('click', () => {
    const box = el.querySelector('#scanPaste'); box.hidden = !box.hidden;
    if (!box.hidden) el.querySelector('#scanText').focus();
  });
  el.querySelector('#scanCheck').addEventListener('click', () => {
    const text = el.querySelector('#scanText').value.trim();
    if (text) check(text, null);
  });
  el.querySelector('#scanFile')?.addEventListener('change', async (e) => {
    const file = e.target.files[0]; if (!file) return;
    if (!file.type.startsWith('image/')) { toast(t('scan.imgOnly', 'Choose an image (a photo or screenshot)'), 'bad'); return; }
    const bar = (pct, label) => { status.innerHTML = `<div class="scan-progress"><p class="tiny quiet">${esc(label)}</p><span class="lift-bar"><i style="width:${pct}%"></i></span></div>`; };
    bar(2, t('scan.loadingOcr', 'Loading the text reader (first time only, about 12 MB)…'));
    try {
      const { text, confidence } = await readImage(file, (m) => {
        if (m.status === 'recognizing text') bar(Math.round(m.progress * 100), t('scan.reading', 'Reading the text… {p}%', { p: Math.round(m.progress * 100) }));
        else if (m.status) bar(Math.max(3, Math.round((m.progress || 0) * 30)), t('scan.loadingOcr', 'Loading the text reader (first time only, about 12 MB)…'));
      });
      if (!text || text.length < 15) { status.innerHTML = ''; toast(t('scan.noText', 'Could not read text from this image. Try a sharper, flatter photo.'), 'bad'); return; }
      if (confidence < 45) toast(t('scan.lowConf', 'The photo is hard to read ({p}% confidence). Results may be off.', { p: confidence }));
      await check(text, file);
    } catch (err) {
      status.innerHTML = '';
      toast(err.message || t('scan.fail', 'Could not read the image'), 'bad');
    }
    e.target.value = '';
  });
}

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
      <a class="card panel-pad section plan-link" href="#/planner">${icon('list-todo')}<span><strong>${esc(t('pp.linkT', 'Plan when to get each one'))}</strong><br />
        <span class="small quiet">${esc(t('pp.linkP', 'A week-by-week plan that gets the documents unlocking the most schemes first.'))}</span></span>${icon('chevron-right')}</a>
      ${scanner()}
      <section class="card section">${r.total ? table(r.docs) : `<p class="quiet" style="padding:22px">${esc(t('docs.none', 'No documents needed yet.'))}</p>`}</section>
      ${others.length ? `<details class="section"><summary class="h3" style="cursor:pointer">${esc(t('docs.others', 'For schemes you are close to'))} <span class="quiet num">(${others.length})</span></summary>
        <section class="card" style="margin-top:12px">${table(others)}</section></details>` : ''}
      ${Object.keys(state.vault).length ? `<div class="section"><button class="btn btn-danger-quiet" type="button" id="dClear">${icon('trash-2')}${esc(t('docs.clear', 'Remove all files'))}</button></div>` : ''}`;
    animateIn(el);
    bindScanner(el);

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
