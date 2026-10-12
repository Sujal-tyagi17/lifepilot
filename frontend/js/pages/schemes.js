/* Schemes: every match as an expandable slip, plus the What-if simulator. */
import { esc, fmtINR, daysLeft, fmtDate, matchStatus, debounce } from '../util.js';
import { t, getLang } from '../i18n.js';
import { icon, stamp, toast } from '../ui.js';
import { emptyCard, chips, incomeSlider, typeahead, switchRow, bindControls } from '../components.js';
import { genderOptions, eduOptions, matchState } from './start.js';
import { state, hasDoc } from '../state.js';
import { simulate } from '../run.js';
import { STATES, CATEGORIES } from '../profileFields.js';
import { counterfactuals } from '../features.js';

const FILTERS = [
  ['all', 'f.all', 'All', () => true],
  ['eligible', 'f.eligible', 'Eligible', (m) => matchStatus(m) === 'eligible'],
  ['partial', 'f.partial', 'Close', (m) => ['partial', 'needs_review'].includes(matchStatus(m))],
  ['open', 'f.open', 'Open now', (m) => matchStatus(m) !== 'closed'],
];

function deadlineText(m) {
  const d = daysLeft(m.deadline);
  const lang = getLang();
  if (!m.deadline) return esc(m.deadline_note || '');
  if (d < 0) return `<span class="bad">${esc(t('sch.closed', 'Closed {date}, reopens next cycle', { date: fmtDate(m.deadline, lang) }))}</span>`;
  if (d === 0) return `<span class="bad">${esc(t('sch.closesToday', 'Closes today'))}</span>`;
  const txt = esc(t('sch.closes', 'Closes {date} · {days} days', { date: fmtDate(m.deadline, lang), days: d }));
  return d <= 7 ? `<span class="bad">${txt}</span>` : txt;
}

function criteriaList(c) {
  if (!c) return [];
  const out = [];
  if (c.category) out.push(`${t('f.category', 'Category')}: ${c.category.join(', ')}`);
  if (c.education_level) out.push(`${t('f.education', 'Education level')}: ${c.education_level.join(', ')}`);
  if (c.max_income) out.push(`${t('f.income', 'Family income per year (₹)').replace(' (₹)', '')} ≤ ${fmtINR(c.max_income)}`);
  if (c.max_age) out.push(`${t('f.age', 'Age')} ≤ ${c.max_age}`);
  if (c.gender) out.push(`${t('f.gender', 'Gender')}: ${c.gender.join(', ')}`);
  if (c.state) out.push(`${t('f.state', 'State')}: ${c.state.join(', ')}`);
  if (c.field_of_study) out.push(`${t('f.field', 'Field of study')}: ${c.field_of_study.join(', ')}`);
  if (c.disability) out.push(t('f.disability', 'I have a disability of 40% or more'));
  return out;
}

const list = (items, cls, ic) => `<ul class="facts-list">${items.map((x) => `<li class="${cls}">${icon(ic, 'icon-sm')}<span style="color:var(--ink)">${esc(x)}</span></li>`).join('')}</ul>`;

export function slip(m) {
  const st = matchStatus(m);
  const docs = m.documents || [];
  const rules = criteriaList(m.criteria);
  return `<li><details class="slip">
    <summary>
      <div>
        <p class="slip-title">${esc(m.title)}</p>
        <p class="slip-sub">${esc(m.provider || '')}</p>
        <p class="slip-facts">${m.amount ? `<span class="num">${esc(m.amount)}</span>` : ''}<span>${deadlineText(m)}</span></p>
      </div>
      <div class="slip-side">
        ${stamp(st)}
        ${st === 'partial' ? `<span class="tiny quiet">${esc(t('sch.match', '{pct}% of rules met', { pct: Math.round((m.score || 0) * 100) }))}</span>` : ''}
        <span class="slip-chev">${icon('chevron-down')}</span>
      </div>
    </summary>
    <div class="slip-body">
      ${m.description ? `<p class="wide quiet">${esc(m.description)}</p>` : ''}
      ${(m.reasons || []).length ? `<div><h3 class="h3">${esc(t('sch.why', 'Why you qualify'))}</h3>${list(m.reasons, 'ok', 'check')}</div>` : ''}
      ${(m.unmet || []).length ? `<div><h3 class="h3">${esc(t('sch.gaps', 'What is missing'))}</h3>${list(m.unmet, 'gap', 'circle-dashed')}</div>` : ''}
      ${docs.length ? `<div><h3 class="h3">${esc(t('sch.docs', 'Documents needed'))}</h3><ul class="facts-list">${docs.map((d) => hasDoc(d)
        ? `<li class="ok">${icon('circle-check', 'icon-sm')}<span style="color:var(--ink)">${esc(d)}</span></li>`
        : `<li class="quiet">${icon('file-text', 'icon-sm')}<span>${esc(d)}</span></li>`).join('')}</ul></div>` : ''}
      ${rules.length ? `<div><h3 class="h3">${esc(t('sch.rules', 'Eligibility rules'))}</h3>${list(rules, 'quiet', 'info')}</div>` : ''}
      ${(m.roadmap || []).length ? `<div class="wide"><h3 class="h3">${esc(t('sch.steps', 'How to apply'))}</h3><ol class="steps">${m.roadmap.map((s) => `<li>${esc(s)}</li>`).join('')}</ol></div>` : ''}
      ${(m.notes || []).length ? `<div class="wide"><h3 class="h3">${esc(t('sch.notes', 'AI notes (the rules decide)'))}</h3>${list(m.notes, 'quiet', 'info')}</div>` : ''}
      ${m.url ? `<div class="wide"><a class="btn ${st === 'eligible' ? 'btn-primary' : 'btn-secondary'}" href="${esc(m.url)}" target="_blank" rel="noopener noreferrer">${esc(t('sch.portal', 'Open the official portal'))}${icon('external-link', 'icon-sm')}<span class="sr-only"> (opens a new tab)</span></a></div>` : ''}
    </div>
  </details></li>`;
}

export const schemesTabs = (active) => `<div class="segmented" role="tablist" aria-label="${esc(t('nav.schemes', 'Schemes'))}" style="margin-bottom:20px">
  <button type="button" role="tab" aria-pressed="${active === 'matches'}" aria-selected="${active === 'matches'}" data-go="#/schemes">${esc(t('sch.matches', 'Matches'))}</button>
  <button type="button" role="tab" aria-pressed="${active === 'whatif'}" aria-selected="${active === 'whatif'}" data-go="#/schemes/what-if">${esc(t('sch.whatif', 'What if'))}</button>
  <button type="button" role="tab" aria-pressed="${active === 'map'}" aria-selected="${active === 'map'}" data-go="#/schemes/map">${esc(t('sch.map', 'Map'))}</button>
</div>`;

/* ── What would change it? (counterfactual explanations) ── */
const WHATIF_FIELDS = new Set(['education_level', 'field_of_study', 'disability', 'annual_income']);
const KIND_ICON = { later: 'calendar-clock', choice: 'route', document: 'file-text', situation: 'wallet' };

/** The change in Hindi when the app is in Hindi (the server words it in English). */
function changeText(c, j) {
  if (getLang() !== 'hi') return j ? c.text.replace(/^(If|When)\b/, (w) => w.toLowerCase()) : c.text;
  if (c.field === 'education_level') return `जब आप ${c.value} में जाएँगे (अगले सत्र से)`;
  if (c.field === 'field_of_study') return `अगर आप ${c.text.replace(/^If you study /, '').replace(/ or /, ' या ')} पढ़ें`;
  if (c.field === 'disability') return 'अगर आपकी विकलांगता 40% या अधिक है: विकलांगता प्रमाण पत्र (UDID) बनवाएँ';
  if (c.field === 'annual_income') return `अगर आपकी पारिवारिक आय ${fmtINR(c.value)} या कम हो जाए (नए आय प्रमाण पत्र के साथ)`;
  if (c.field === 'goals') return /business|startup/i.test(c.text) ? 'अगर आप अपना व्यवसाय या स्टार्टअप शुरू करना चाहते हैं' : `अगर आपके लक्ष्यों में ${c.text.replace(/^If your goals include /, '')} शामिल हो`;
  return c.text;
}

function cfItem(sug, i) {
  const tryable = sug.changes.every((c) => WHATIF_FIELDS.has(c.field));
  const unlocks = sug.unlocks.map((u) => u.title);
  return `<li class="cf-item">
    <span class="cf-icon">${icon(KIND_ICON[sug.changes[0].kind] || 'sparkle', 'icon-sm')}</span>
    <div style="min-width:0">
      <p class="cf-change">${sug.changes.map((c, j) => esc(changeText(c, j))).join(` <span class="quiet">${esc(t('cf.and', 'and'))}</span> `)}</p>
      <p class="small"><strong class="ok">${esc(sug.count === 1 ? t('cf.unlockOne', '+1 scheme') : t('cf.unlockN', '+{n} schemes', { n: sug.count }))}</strong>
        ${sug.value ? `<span class="quiet"> · ${esc(t('cf.worth', 'about {amount} a year', { amount: fmtINR(sug.value) }))}</span>` : ''}</p>
      <p class="tiny quiet">${esc(unlocks.slice(0, 3).join(' · '))}${unlocks.length > 3 ? ` +${unlocks.length - 3}` : ''}</p>
    </div>
    ${tryable ? `<button class="btn btn-quiet btn-sm" type="button" data-cf="${i}">${esc(t('cf.try', 'Try it'))}${icon('arrow-right', 'icon-sm')}</button>` : '<span></span>'}
  </li>`;
}

async function drawCounterfactuals(box) {
  if (!box || !state.profileId) return;
  box.innerHTML = `<p class="working quiet small" style="padding:16px 22px"><span class="spinner"></span>${esc(t('cf.loading', 'Trying small changes to your profile…'))}</p>`;
  let res;
  try { res = await counterfactuals(); } catch (err) { box.innerHTML = `<p class="small bad" style="padding:16px 22px">${esc(err.message)}</p>`; return; }
  if (!box.isConnected) return;
  const sugs = res.suggestions || [];
  box.innerHTML = sugs.length
    ? `<ul class="cf-list">${sugs.map(cfItem).join('')}</ul>
       <p class="notice tiny" style="margin:0 22px 18px">${icon('shield-check', 'icon-sm')}<span>${esc(t('cf.note', 'Suggestions are about documents you can get or changes in your situation. Always report your details truthfully. Caste, gender, age and state are never suggested.'))}</span></p>`
    : `<p class="quiet small" style="padding:16px 22px">${esc(t('cf.none', 'No small change would unlock another open scheme right now.'))}</p>`;
  box.querySelectorAll('[data-cf]').forEach((b) => b.addEventListener('click', () => {
    const sug = sugs[+b.dataset.cf];
    const p = state.profile || {};
    scenario = { ...p, annual_income: p.annual_income ?? 300000 };
    sug.changes.forEach((c) => { scenario[c.field] = c.field === 'field_of_study' ? String(c.value) : c.value; });
    location.hash = '#/schemes/what-if';
  }));
}

function bindTabs(el) {
  el.querySelectorAll('[data-go]').forEach((b) => b.addEventListener('click', () => { location.hash = b.dataset.go; }));
}

let filter = 'all';
let query = '';
let cfOpen = true;

export const schemes = {
  title: () => t('nav.schemes', 'Schemes'),
  sub: () => t('sch.sub', 'Every scholarship and scheme checked against your profile, with the reasons.'),
  deps: ['run', 'vault', 'ownedDocs'],
  render(el, params) {
    if (params.get('filter')) filter = params.get('filter');
    if (!state.run) {
      el.innerHTML = schemesTabs('matches') + emptyCard({ iconName: 'landmark', title: t('sch.noRun', 'Fill in your profile first to see schemes.'), action: `<a class="btn btn-primary" href="#/start">${esc(t('land.start', 'Get started free'))}</a>` });
      bindTabs(el);
      return;
    }
    const all = state.run.matches || [];
    el.innerHTML = `${schemesTabs('matches')}
      <div class="toolbar">
        <label class="input-icon"><span class="sr-only">${esc(t('sch.search', 'Search schemes or departments'))}</span>${icon('search')}
          <input class="input" type="search" id="sQuery" value="${esc(query)}" placeholder="${esc(t('sch.search', 'Search schemes or departments'))}" /></label>
        <div class="segmented" role="group" aria-label="Filter">${FILTERS.map(([k, key, en, fn]) =>
          `<button type="button" aria-pressed="${filter === k}" data-filter="${k}">${esc(t(key, en))}<span class="count num">${all.filter(fn).length}</span></button>`).join('')}</div>
      </div>
      <details class="card cf-card" id="sCf" ${cfOpen ? 'open' : ''}>
        <summary class="panel-head" style="cursor:pointer"><h2 class="h3">${icon('wand-sparkles', 'icon-sm')} ${esc(t('cf.title', 'What would change it?'))}</h2>
          <span class="tiny quiet">${esc(t('cf.sub', 'Small honest changes that unlock more schemes'))}</span></summary>
        <div id="sCfBody"></div>
      </details>
      <section class="card section"><ul class="rows" id="sList"></ul></section>`;
    bindTabs(el);
    const cfBox = el.querySelector('#sCf');
    if (cfOpen) drawCounterfactuals(el.querySelector('#sCfBody'));
    cfBox.addEventListener('toggle', () => {
      cfOpen = cfBox.open;
      if (cfOpen && !el.querySelector('#sCfBody').innerHTML) drawCounterfactuals(el.querySelector('#sCfBody'));
    });

    const draw = () => {
      const fn = (FILTERS.find(([k]) => k === filter) || FILTERS[0])[3];
      const q = query.toLowerCase();
      const items = all.filter(fn).filter((m) => !q || `${m.title} ${m.provider || ''}`.toLowerCase().includes(q));
      el.querySelector('#sList').innerHTML = items.length ? items.map(slip).join('')
        : `<li><p class="quiet" style="padding:20px">${esc(t('sch.empty', 'No schemes match this filter.'))}</p></li>`;
    };
    draw();
    el.querySelector('#sQuery').addEventListener('input', (e) => { query = e.target.value; draw(); });
    el.querySelectorAll('[data-filter]').forEach((b) => b.addEventListener('click', () => {
      filter = b.dataset.filter;
      el.querySelectorAll('[data-filter]').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
      draw();
    }));
  },
};

/* ── What if ── */
let scenario = null;

export const whatIf = {
  title: () => t('sch.whatifT', 'What if…?'),
  sub: () => t('wi.lede', 'Change income, category or studies to see how your results change. Nothing is saved.'),
  deps: [],
  render(el) {
    const p = state.profile || {};
    if (!scenario) scenario = { ...p, annual_income: p.annual_income ?? 300000 };
    const s = scenario;
    el.innerHTML = `${schemesTabs('whatif')}
      <div class="whatif">
        <form class="card panel-pad stack" id="wiForm" style="margin-top:0">
          ${incomeSlider('annual_income', s.annual_income, { label: t('wi.income', 'Family income per year') })}
          ${chips('category', CATEGORIES.map((c) => [c, c]), s.category, { label: t('f.category', 'Category'), id: 'wiCat' })}
          ${chips('education_level', eduOptions().map(([v, l]) => [v, l]), s.education_level, { label: t('f.education', 'Education level'), id: 'wiEdu' })}
          ${chips('gender', genderOptions(), s.gender, { label: t('f.gender', 'Gender'), id: 'wiGender' })}
          ${typeahead('state', STATES, s.state, { label: t('f.state', 'State'), placeholder: t('ob.statePh', 'Start typing your state') })}
          <div class="field"><label class="label" for="wiField">${esc(t('f.field', 'Field of study'))}</label>
            <input class="input" id="wiField" name="field_of_study" value="${esc(s.field_of_study || '')}" /></div>
          ${switchRow('disability', t('f.disability', 'I have a disability of 40% or more'), s.disability)}
          <button class="btn btn-quiet" type="button" id="wiReset">${icon('arrow-left')}${esc(t('wi.reset', 'Back to my profile'))}</button>
        </form>
        <div class="stack" style="margin-top:0;position:sticky;top:92px">
          <div class="figures" aria-live="polite">
            <div class="card figure"><p class="figure-value num" id="wiElig">–</p><p class="figure-label">${esc(t('wi.eligible', 'Schemes you qualify for'))}</p></div>
            <div class="card figure"><p class="figure-value num" id="wiBen">–</p><p class="figure-label">${esc(t('wi.perYear', 'a year'))}</p></div>
            <div class="card figure"><p class="figure-value num" id="wiDelta">–</p><p class="figure-label">${esc(t('wi.vsYou', 'Compared with your profile'))}</p></div>
          </div>
          <section class="card" aria-labelledby="wiListH">
            <div class="panel-head"><h2 class="h3" id="wiListH">${esc(t('wi.list', 'Schemes you would qualify for'))}</h2></div>
            <ul class="rows" id="wiList"></ul>
          </section>
        </div>
      </div>`;
    bindTabs(el);

    const form = el.querySelector('#wiForm');
    bindControls(form);
    const read = () => {
      const fd = new FormData(form);
      scenario = {
        ...p,
        annual_income: Number(fd.get('annual_income')),
        category: fd.get('category') || null, education_level: fd.get('education_level') || null,
        gender: fd.get('gender') || null, state: matchState(fd.get('state')),
        field_of_study: (fd.get('field_of_study') || '').trim() || null, disability: fd.get('disability') === 'on',
      };
    };
    const run = debounce(async () => {
      try {
        const res = await simulate({ ...scenario, name: p.name || 'What-if' });
        const ins = res.insights;
        const base = state.run?.insights;
        el.querySelector('#wiElig').textContent = ins.eligible_count;
        el.querySelector('#wiBen').textContent = fmtINR(ins.estimated_annual_benefit);
        const dE = base ? ins.eligible_count - base.eligible_count : null;
        const dB = base ? ins.estimated_annual_benefit - base.estimated_annual_benefit : null;
        const delta = el.querySelector('#wiDelta');
        delta.textContent = dE === null ? '–'
          : dE === 0 && dB === 0 ? t('wi.same', 'No change')
            : `${dE > 0 ? '+' : ''}${dE} · ${dB > 0 ? '+' : dB < 0 ? '−' : ''}${fmtINR(Math.abs(dB))}`;
        delta.className = `figure-value num ${dE > 0 || dB > 0 ? 'ok' : dE < 0 || dB < 0 ? 'bad' : ''}`;
        const elig = res.matches.filter((m) => matchStatus(m) === 'eligible');
        el.querySelector('#wiList').innerHTML = elig.length
          ? elig.map((m) => `<li class="row" style="padding:14px 22px;animation:enter .35s var(--ease) both"><div style="flex:1;min-width:0"><p style="font-weight:620">${esc(m.title)}</p><p class="small quiet num">${esc(m.amount || '')}</p></div>${stamp('eligible')}</li>`).join('')
          : `<li><p class="quiet" style="padding:16px 20px">${esc(t('wi.none', 'No scheme matches this scenario.'))}</p></li>`;
      } catch (err) { toast(err.message, 'bad'); }
    }, 200);

    form.addEventListener('input', () => { read(); run(); });
    el.querySelector('#wiReset').addEventListener('click', () => { scenario = null; whatIf.render(el); });
    run();
  },
};
