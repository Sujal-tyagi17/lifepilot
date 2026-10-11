/* ML Lab: the examiner's view. Real metrics from metrics.json, live predictions with reasons, labelling. */
import { esc } from '../util.js';
import { t } from '../i18n.js';
import { icon, toast } from '../ui.js';
import { api } from '../api.js';
import { animateIn } from '../components.js';

const ORDER = ['fit', 'role', 'skills', 'intent', 'document', 'search'];
const ICONS = { fit: 'gauge', role: 'briefcase', skills: 'list-checks', intent: 'message-circle', document: 'file-search', search: 'search' };
const FEATURE_NAMES = {
  must: ['seg.must', 'Must-have skills'], nice: ['seg.nice', 'Good to have'], role: ['seg.role', 'Role'], experience: ['seg.experience', 'Experience'],
  education: ['seg.education', 'Education'], field: ['seg.field', 'Field'], text: ['seg.text', 'Resume wording'],
};
const TRY = [
  ['fit', 'ml.tryFit', 'Job fit'], ['role', 'ml.tryRole', 'Role family'], ['intent', 'ml.tryIntent', 'Chat intent'],
  ['skills', 'ml.trySkills', 'Skills'], ['document', 'ml.tryDoc', 'Document type'], ['describe', 'ml.tryDescribe', 'Describe yourself'],
];
const EXAMPLES = {
  role: 'We need someone to run our Instagram and Google ads, plan campaigns and grow website traffic with SEO.',
  intent: 'form kab tak bharna hai?',
  skills: 'Skills: Pyhton, Javascrpt, MS Excel\nProjects: dashboard in Power BI with SQL\nExperience: intern, built REST APIs with FastAPI',
  document: 'Government of Karnataka Revenue Department Income Certificate No K123456 annual income Rs 2,40,000 Tehsildar',
  describe: "I'm Aisha, a 21-year-old girl from Bengaluru doing B.Tech in computer science, OBC, family income 3 lakh, I want a job",
  job: 'Data analyst. Requirements: Excel, SQL, Power BI, Statistics. Experience: 0-2 years. Education: Bachelor\'s degree.',
  resume: 'Skills\nExcel, SQL, Python\nProjects\nSales dashboard in Power BI\nEducation\nB.Com 2022-2025',
};

let metrics = null;
let tryTab = 'fit';
let pair = null;
let busy = false;

const pct = (x) => (x == null ? '—' : `${Math.round(x * 100)}%`);

function primary(m) {
  const tst = m.test || {};
  if (tst.recall_at_5 != null) return [['ml.recall5', 'Recall@5', tst.recall_at_5]];
  if (tst.precision != null) return [['ml.precision', 'Precision', tst.precision], ['ml.recall', 'Recall', tst.recall]];
  return [['ml.accuracy', 'Accuracy', tst.accuracy], ['ml.f1', 'Macro F1', tst.macro_f1]];
}

function baselineValue(m) {
  const b = m.rules_baseline;
  if (!b) return null;
  return b.recall_at_5 ?? b.accuracy ?? b.f1 ?? null;
}

function compareBars(m) {
  const ml = (m.test || {}).recall_at_5 ?? (m.test || {}).accuracy ?? (m.test || {}).f1;
  const rules = baselineValue(m);
  if (ml == null || rules == null) return '';
  const label = m.rules_baseline.recall_at_5 != null ? t('ml.keywordSearch', 'Keyword search') : m.test.f1 != null ? t('ml.exactOnly', 'Exact matching only') : t('ml.rules', 'Old rules');
  return `<div class="cmp">
    <div><span class="tiny quiet">${esc(t('ml.model', 'Model'))}</span><span class="cmp-bar"><i class="ml" style="width:0" data-width="${ml * 100}%"></i></span><b class="num">${pct(ml)}</b></div>
    <div><span class="tiny quiet">${esc(label)}</span><span class="cmp-bar"><i style="width:0" data-width="${rules * 100}%"></i></span><b class="num">${pct(rules)}</b></div>
  </div>`;
}

function confusion(cm, labels) {
  if (!cm || !labels) return '';
  const max = Math.max(1, ...cm.flat());
  return `<details class="cm"><summary>${icon('layers', 'icon-sm')} ${esc(t('ml.cm', 'Confusion matrix (test set)'))}</summary>
    <div class="cm-scroll"><table><thead><tr><th class="tiny quiet">${esc(t('ml.trueVsPred', 'true ↓ / predicted →'))}</th>${labels.map((l) => `<th title="${esc(l)}">${esc(l.slice(0, 6))}</th>`).join('')}</tr></thead>
    <tbody>${cm.map((row, i) => `<tr><th title="${esc(labels[i])}">${esc(labels[i])}</th>${row.map((v, j) => `<td class="${i === j ? 'diag' : v ? 'off' : ''}" style="--a:${(v / max).toFixed(2)}">${v || ''}</td>`).join('')}</tr>`).join('')}</tbody></table></div></details>`;
}

function weightsChart(w) {
  if (!w) return '';
  const max = Math.max(...Object.values(w.hand_set), ...Object.values(w.learned));
  return `<div class="wchart"><p class="tiny quiet" style="margin-bottom:6px">${esc(t('ml.weights', 'Fit-score weights: hand-set (grey) vs learned by the model (indigo)'))}</p>
    ${Object.keys(w.learned).map((f) => `<div class="wrow"><span class="small">${esc(t(...FEATURE_NAMES[f]))}</span>
      <span class="wbars"><i style="width:0" data-width="${(w.hand_set[f] / max) * 100}%"></i><i class="ml" style="width:0" data-width="${(w.learned[f] / max) * 100}%"></i></span>
      <span class="tiny num">${Math.round(w.hand_set[f] * 100)} → <b>${Math.round(w.learned[f] * 100)}</b></span></div>`).join('')}</div>`;
}

function modelCard(key, m) {
  const d = m.dataset || {};
  const facts = [
    d.rows != null && t('ml.rows', '{n} examples', { n: d.rows }),
    d.classes != null && (typeof d.classes === 'number' ? t('ml.classes', '{n} classes', { n: d.classes }) : Object.entries(d.classes).map(([k, v]) => `${k} ${v}`).join(' · ')),
    d.train != null && t('ml.split', 'train {a} / test {b}', { a: d.train, b: d.test }),
    d.dictionary_skills && t('ml.dict', '{n} skills, {a} aliases', { n: d.dictionary_skills, a: d.aliases }),
    d.team_labels && t('ml.team', '{n} team labels', { n: d.team_labels }),
    d.file,
  ].filter(Boolean);
  const extra = [];
  if (m.cv5) extra.push(`<p class="small">${icon('refresh-cw', 'icon-sm')} ${esc(t('ml.cv', '5-fold cross-validation: {m}% ± {s}', { m: Math.round(m.cv5.mean * 100), s: Math.round(m.cv5.std * 100) }))}</p>`);
  if (m.unseen_real_roles) extra.push(`<p class="small">${icon('target', 'icon-sm')} ${esc(t('ml.unseen', 'On {n} hand-written roles it never saw in training: {a} accuracy', { n: m.unseen_real_roles.rows, a: pct(m.unseen_real_roles.accuracy) }))}</p>`);
  if (m.learned_weights_test) extra.push(`<p class="small">${icon('gauge', 'icon-sm')} ${esc(t('ml.learnedW', 'The app\'s fit score with the learned weights: {a} accuracy (old weights: {b})', { a: pct(m.learned_weights_test.accuracy), b: pct(m.rules_baseline.accuracy) }))}</p>`);
  if (m.note) extra.push(`<p class="tiny quiet">${esc(m.note)}</p>`);
  const metricsHtml = m.test
    ? `<div class="ml-nums">${primary(m).map(([k, en, v]) => `<div><b class="num">${pct(v)}</b><span class="tiny quiet">${esc(t(k, en))}</span></div>`).join('')}</div>${compareBars(m)}`
    : `<p class="notice notice-warn small">${icon('info', 'icon-sm')} ${esc(m.skipped || t('ml.notRun', 'Not evaluated yet'))}. ${esc(t('ml.runTrain', 'Run python -m app.ml.train on your computer to measure it.'))}</p>`;
  return `<article class="card ml-card">
    <header class="ml-head"><span class="ml-icon">${icon(ICONS[key])}</span><div><h3 class="h3">${esc(m.name)}</h3><p class="tiny quiet">${esc(m.type)}</p></div></header>
    <p class="small">${esc(m.used_for)}</p>
    ${metricsHtml}
    <div class="facts">${facts.map((f) => `<span>${esc(f)}</span>`).join('')}</div>
    ${key === 'fit' ? weightsChart(m.weights) : ''}
    ${extra.join('')}
    ${m.test?.confusion_matrix ? confusion(m.test.confusion_matrix, m.test.labels) : ''}
  </article>`;
}

/* ── Try it live ── */
function tryPanel() {
  if (tryTab === 'fit') return `
    <div class="grid-2">
      <div class="field"><label class="label" for="tJob">${esc(t('ml.job', 'Job post (first sentence is the title)'))}</label><textarea class="textarea" id="tJob" rows="5">${esc(EXAMPLES.job)}</textarea></div>
      <div class="field"><label class="label" for="tResume">${esc(t('ml.resume', 'Resume text'))}</label><textarea class="textarea" id="tResume" rows="5">${esc(EXAMPLES.resume)}</textarea></div>
    </div>
    <div class="field"><label class="label" for="tRole">${esc(t('jobs.role', 'Role you want'))}</label><input class="input" id="tRole" value="Data analyst" /></div>`;
  return `<div class="field"><label class="label" for="tText">${esc(t('ml.input', 'Text'))}</label>
    <textarea class="textarea" id="tText" rows="${tryTab === 'intent' || tryTab === 'describe' ? 2 : 4}">${esc(EXAMPLES[tryTab])}</textarea></div>`;
}

const because = (list) => (list || []).length
  ? `<p class="tiny quiet" style="margin-top:10px">${esc(t('ml.because', 'Words that pushed it there'))}</p><div class="skills">${list.map((w) => `<span class="skill ev">${esc(w.term)} <span class="quiet num">+${w.weight}</span></span>`).join('')}</div>` : '';

const topList = (top, nameKey = 'label') => `<div class="top3">${(top || []).map((x) => `<div><span class="small">${esc(x.label_name || x[nameKey])}</span><span class="cmp-bar"><i class="ml" style="width:0" data-width="${x.score * 100}%"></i></span><b class="num small">${pct(x.score)}</b></div>`).join('')}</div>`;

function showResult(box, res) {
  let html = '';
  if (tryTab === 'role') {
    const m = res.model;
    html = m ? `<p class="result-head">${icon('briefcase')} <b>${esc(m.label_name || m.label)}</b> <span class="quiet small">${pct(m.confidence)}</span></p>${topList(m.top)}${because(m.because)}
      <p class="tiny quiet" style="margin-top:10px">${esc(t('ml.rulesSaid', 'Old keyword rules said: {r}', { r: res.rules.label_name || t('ml.noMatch', 'no match') }))}</p>` : t('ml.noModel', 'Model not trained.');
  } else if (tryTab === 'intent') {
    const m = res.model;
    html = m ? `<p class="result-head">${icon('message-circle')} <b>${esc(m.label)}</b> <span class="quiet small">${pct(m.confidence)}</span></p>${topList(m.top)}${because(m.because)}` : t('ml.noModel', 'Model not trained.');
  } else if (tryTab === 'document') {
    const m = res.model;
    html = m ? `<p class="result-head">${icon('file-search')} <b>${esc(m.label)}</b> <span class="quiet small">${pct(m.confidence)}</span></p>${topList(m.top)}${because(m.because)}` : t('ml.noModel', 'Model not trained.');
  } else if (tryTab === 'skills') {
    html = `<p class="tiny quiet">${esc(t('ml.exact', 'Exact matches'))}</p><div class="skills">${res.exact.map((s) => `<span class="skill">${esc(s)}</span>`).join('') || '—'}</div>
      <p class="tiny quiet" style="margin-top:10px">${esc(t('ml.fuzzy', 'Found despite a typo (fuzzy matching)'))}</p><div class="skills">${res.fuzzy.map((s) => `<span class="skill ev ev-listed">${esc(s)}</span>`).join('') || '—'}</div>
      <p class="tiny quiet" style="margin-top:10px">${esc(t('ml.strength', 'Strength from where it appears'))}</p><div class="skills">${res.resume.map((s) => `<span class="skill ev ev-${esc(s.evidence)}">${esc(s.name)} · ${esc(s.evidence)}</span>`).join('')}</div>`;
  } else if (tryTab === 'describe') {
    html = `<div class="skills">${res.found.map((f) => `<span class="skill" title="${esc(f.from)}">${esc(f.field)}: <b>${esc(String(f.value))}</b> <span class="quiet">← “${esc(f.from)}”</span></span>`).join('') || '—'}</div>
      ${res.missing.length ? `<p class="tiny quiet" style="margin-top:8px">${esc(t('ml.missing', 'Not found: {f}', { f: res.missing.join(', ') }))}</p>` : ''}`;
  } else if (tryTab === 'fit') {
    const p = res.probabilities || {};
    html = `<div class="ml-nums"><div><b class="num">${pct(res.learned_fit)}</b><span class="tiny quiet">${esc(t('ml.learnedFit', 'Fit, learned weights'))}</span></div>
        <div><b class="num quiet">${pct(res.rules_fit)}</b><span class="tiny quiet">${esc(t('ml.rulesFit', 'Fit, old weights'))}</span></div></div>
      ${p.Good != null ? `<p class="tiny quiet" style="margin-top:8px">${esc(t('ml.probs', 'Logistic regression: chance of each label'))}</p>${topList(['Good', 'Okay', 'Poor'].map((l) => ({ label: l, score: p[l] })))}` : ''}
      <p class="tiny quiet" style="margin-top:10px">${esc(t('ml.featuresT', 'Features for this pair (0–1)'))}</p>
      <div class="skills">${Object.entries(res.features).map(([k, v]) => `<span class="skill ev">${esc(t(...FEATURE_NAMES[k]))}: ${v}</span>`).join('')}</div>`;
  }
  box.innerHTML = html;
  animateIn(box);
}

async function runTry(el) {
  const box = el.querySelector('#tryOut');
  box.innerHTML = '<span class="spinner"></span>';
  try {
    let res;
    if (tryTab === 'fit') {
      res = await api('/api/ml/predict/fit', { method: 'POST', json: { job_text: el.querySelector('#tJob').value, resume_text: el.querySelector('#tResume').value, target_role: el.querySelector('#tRole').value } });
    } else {
      const path = tryTab === 'describe' ? '/api/ml/describe' : `/api/ml/predict/${tryTab}`;
      res = await api(path, { method: 'POST', json: { text: el.querySelector('#tText').value } });
    }
    showResult(box, res);
  } catch (err) { box.innerHTML = `<p class="notice notice-warn">${esc(err.message)}</p>`; }
}

/* ── Label and retrain ── */
function labelCard() {
  if (!pair) return `<p class="quiet small"><span class="spinner"></span></p>`;
  if (!pair.pair) return `<p class="small">${esc(t('ml.allLabelled', 'Every seed pair has a team label. Retrain to use them.'))}</p>`;
  const p = pair.pair;
  return `
    <p class="tiny quiet">${esc(t('ml.progress', '{d} of {n} pairs labelled by the team', { d: pair.done, n: pair.total }))}</p>
    <div class="grid-2" style="margin-top:8px">
      <div class="pair-box"><p class="tiny quiet">${esc(t('ml.theJob', 'Job'))}</p><p><b>${esc(p.job_title)}</b></p><p class="small">${esc(p.job_text)}</p></div>
      <div class="pair-box"><p class="tiny quiet">${esc(t('ml.theResume', 'Resume'))} · ${esc(t('ml.wants', 'wants: {r}', { r: p.target_role }))} · ${esc(p.education_level)}</p><pre class="small">${esc(p.resume_text)}</pre></div>
    </div>
    <p class="small" style="margin-top:10px">${esc(t('ml.seedSays', 'Seed label from the rubric: {l}. What do you say?', { l: p.label }))}</p>
    <div class="row row-wrap" style="gap:8px;margin-top:8px">
      ${['Good', 'Okay', 'Poor'].map((l) => `<button class="btn ${l === 'Good' ? 'btn-primary' : 'btn-secondary'} btn-sm" type="button" data-label="${l}">${esc(l)}</button>`).join('')}
      <button class="btn btn-quiet btn-sm" type="button" id="lSkip">${esc(t('ml.skip', 'Skip'))}</button>
      <input class="input input-sm" id="lName" placeholder="${esc(t('ml.yourName', 'Your name'))}" style="max-width:160px" />
    </div>`;
}

async function loadPair(el) {
  try { pair = await api('/api/ml/label/next'); } catch (err) { pair = { pair: null, done: 0, total: 0 }; toast(err.message, 'bad'); }
  const box = el.querySelector('#labelBox'); if (!box) return;
  box.innerHTML = labelCard();
  box.querySelectorAll('[data-label]').forEach((b) => b.addEventListener('click', async () => {
    try {
      await api('/api/ml/label', { method: 'POST', json: { ...pair.pair, label: b.dataset.label, labelled_by: box.querySelector('#lName').value || 'team' } });
      toast(t('ml.saved', 'Label saved'));
      loadPair(el);
    } catch (err) { toast(err.message, 'bad'); }
  }));
  box.querySelector('#lSkip')?.addEventListener('click', () => loadPair(el));
}

function page(el) {
  const m = metrics;
  if (!m) { el.innerHTML = `<div class="card panel-pad"><span class="spinner"></span></div>`; return; }
  if (!m.trained) {
    el.innerHTML = `<div class="card empty"><span class="empty-icon">${icon('bot', 'icon-lg')}</span><h2 class="h2">${esc(t('ml.notTrained', 'The models are not trained yet'))}</h2>
      <p class="quiet">${esc(t('ml.trainHow', 'In the backend folder run: python -m app.ml.train'))}</p></div>`;
    return;
  }
  el.innerHTML = `
    <div class="ml-meta">${[t('ml.six', '6 models'), t('ml.trained', 'trained {d}', { d: m.trained_at }), `scikit-learn ${m.sklearn}`, m.split].map((x) => `<span>${esc(x)}</span>`).join('')}</div>
    <div class="ml-principles">
      ${[['scale', 'ml.p1t', 'Small data, simple models', 'ml.p1', 'With hundreds of examples, TF-IDF with a linear model beats deep learning and trains in seconds on a laptop.'],
         ['eye', 'ml.p2t', 'Explainable by design', 'ml.p2', 'Linear models expose their weights, so every prediction shows the words or features that drove it.'],
         ['landmark', 'ml.p3t', 'Rules where the law is a rule', 'ml.p3', 'Scheme eligibility stays rule-based. ML is used for reading, matching and ranking.']]
        .map(([ic, k1, e1, k2, e2]) => `<div class="card panel-pad"><span class="ml-icon">${icon(ic)}</span><h3 class="h3">${esc(t(k1, e1))}</h3><p class="small quiet">${esc(t(k2, e2))}</p></div>`).join('')}
    </div>

    <h2 class="h2 section-title">${esc(t('ml.modelsT', 'The models'))}</h2>
    <div class="ml-grid">${ORDER.filter((k) => m.models[k]).map((k) => modelCard(k, m.models[k])).join('')}</div>

    <h2 class="h2 section-title">${esc(t('ml.tryT', 'Try it live'))}</h2>
    <section class="card panel-pad">
      <div class="segmented ml-tabs" role="tablist">${TRY.map(([k, key, en]) => `<button type="button" role="tab" data-try="${k}" aria-pressed="${tryTab === k}" aria-selected="${tryTab === k}">${esc(t(key, en))}</button>`).join('')}</div>
      <div id="tryIn" style="margin-top:14px">${tryPanel()}</div>
      <div class="row" style="margin-top:12px"><button class="btn btn-primary" type="button" id="tryGo">${icon('play', 'icon-sm')}${esc(t('ml.run', 'Run the model'))}</button></div>
      <div id="tryOut" class="try-out" aria-live="polite"></div>
    </section>

    <h2 class="h2 section-title">${esc(t('ml.labelT', 'Label data and retrain'))}</h2>
    <section class="card panel-pad">
      <p class="small quiet">${esc(t('ml.labelLede', 'The seed labels come from a written rubric (app/ml/data/LABELLING.md). Relabel pairs as a team; your labels override the seed ones when you retrain.'))}</p>
      <div id="labelBox" style="margin-top:12px">${labelCard()}</div>
      <div class="row row-wrap" style="margin-top:16px;gap:10px;align-items:center">
        <button class="btn btn-secondary" type="button" id="retrain" ${busy ? 'disabled' : ''}>${busy ? '<span class="spinner"></span>' : icon('refresh-cw', 'icon-sm')}${esc(t('ml.retrain', 'Retrain all models'))}</button>
        <span class="tiny quiet">${esc(t('ml.retrainNote', 'About 20 seconds. Same as running python -m app.ml.train.'))}</span>
      </div>
    </section>`;
  animateIn(el);
  el.querySelectorAll('[data-try]').forEach((b) => b.addEventListener('click', () => {
    tryTab = b.dataset.try;
    el.querySelectorAll('[data-try]').forEach((x) => { x.setAttribute('aria-pressed', String(x === b)); x.setAttribute('aria-selected', String(x === b)); });
    el.querySelector('#tryIn').innerHTML = tryPanel();
    el.querySelector('#tryOut').innerHTML = '';
  }));
  el.querySelector('#tryGo').addEventListener('click', () => runTry(el));
  el.querySelector('#retrain').addEventListener('click', async () => {
    busy = true; page(el);
    try {
      await api('/api/ml/retrain', { method: 'POST' });
      metrics = await api('/api/ml/metrics');
      toast(t('ml.retrained', 'Models retrained'));
    } catch (err) { toast(err.message, 'bad'); }
    busy = false; page(el); loadPair(el);
  });
  loadPair(el);
}

export const mlLab = {
  title: () => t('ml.title', 'ML Lab'),
  sub: () => t('ml.sub', 'Every model in LifePilot: what it does, the data it learned from, how well it does, and a box to try it yourself.'),
  deps: [],
  render(el) {
    page(el);
    if (!metrics) {
      api('/api/ml/metrics').then((m) => { metrics = m; page(el); }).catch((err) => { el.innerHTML = `<p class="notice notice-warn">${esc(err.message)}</p>`; });
    }
  },
};
