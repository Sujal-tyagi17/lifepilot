/* Home: your file. One sentence verdict, what to do this week, deadlines, documents. */
import { esc, fmtINR, daysLeft, fmtDate, matchStatus } from '../util.js';
import { t, getLang } from '../i18n.js';
import { icon, stamp, skeleton, emptyState } from '../ui.js';
import { state, eligibleMatches, readiness, hasDoc } from '../state.js';
import { runAgents } from '../run.js';
import { downloadCalendar, printPlan } from '../print.js';
import { EDUCATION } from '../profileFields.js';

let stampedRunId = null; // the stamp animation plays once per new result, not on every visit

function verdictSentence(ins) {
  const n = ins.eligible_count;
  const amount = ins.estimated_annual_benefit;
  if (n === 0) return t('home.qualifyNone', 'No open scheme fully matches you yet.');
  if (!amount) return t('home.qualifyNoAmount', 'You qualify for {n} schemes.', { n });
  if (n === 1) return t('home.qualifyOne', 'You qualify for 1 scheme worth {amount} a year.', { amount: fmtINR(amount) });
  return t('home.qualify', 'You qualify for {n} schemes worth {amount} a year.', { n, amount: fmtINR(amount) });
}

function fileFields() {
  const p = state.profile || {};
  const edu = EDUCATION.find(([v]) => v === p.education_level);
  const fields = [
    ['f.education', 'Education', edu ? (getLang() === 'hi' ? edu[2] : edu[1]) : null],
    ['f.category', 'Category', p.category],
    ['f.state', 'State', p.state],
    ['f.income', 'Family income per year (₹)', p.annual_income != null ? fmtINR(p.annual_income) : null],
  ];
  return `<dl class="file-fields">${fields.map(([k, en, v]) => `
    <div class="file-field"><dt>${esc(t(k, en).replace(' (₹)', ''))}</dt><dd>${v ? esc(v)
      : `<a class="blank" href="#/profile">${icon('plus', 'icon-sm')}${esc(t('home.addMissing', 'Add'))}</a>`}</dd></div>`).join('')}</dl>`;
}

/** Up to four next actions, most urgent first. Every item comes from real data. */
export function priorities() {
  const items = [];
  const elig = eligibleMatches()
    .map((m) => ({ m, d: daysLeft(m.deadline) }))
    .filter(({ d }) => d !== null && d >= 0)
    .sort((a, b) => a.d - b.d);

  for (const { m, d } of elig.slice(0, 2)) {
    items.push({
      urgency: d,
      title: t('todo.apply', 'Apply for {title}', { title: m.title }),
      meta: d === 0
        ? t('todo.applyToday', 'Closes today · {amount}', { amount: m.amount || '' })
        : t('todo.applyMeta', 'Closes in {days} days · {amount}', { days: d, amount: m.amount || '' }),
      action: m.url ? `<a class="btn btn-primary btn-sm" href="${esc(m.url)}" target="_blank" rel="noopener noreferrer">${esc(t('btn.apply', 'Apply'))}${icon('external-link', 'icon-sm')}<span class="sr-only"> (opens a new tab)</span></a>` : '',
    });
  }

  const missing = readiness().docs.filter((d) => !hasDoc(d.document));
  if (missing.length) {
    const d = missing[0];
    items.push({
      urgency: 20,
      title: t('todo.doc', 'Get your {doc} ready', { doc: d.document }),
      meta: d.used_by === 1 ? t('todo.docMetaOne', 'Needed by 1 scheme') : t('todo.docMeta', 'Needed by {n} schemes', { n: d.used_by }),
      action: `<a class="btn btn-secondary btn-sm" href="#/documents">${esc(t('btn.upload', 'Upload'))}</a>`,
    });
  }

  const p = state.profile || {};
  const gap = [['state', 'f.state', 'State'], ['category', 'f.category', 'Category'], ['annual_income', 'f.income', 'family income'], ['education_level', 'f.education', 'Education level']]
    .find(([k]) => p[k] == null || p[k] === '');
  if (gap) {
    items.push({
      urgency: 25,
      title: t('todo.profile', 'Add your {field} to your profile', { field: t(gap[1], gap[2]).replace(' (₹)', '').toLowerCase() }),
      meta: t('todo.profileMeta', 'Many schemes decide eligibility on this.'),
      action: `<a class="btn btn-secondary btn-sm" href="#/profile">${esc(t('btn.add', 'Add'))}</a>`,
    });
  }

  const top = state.jobs?.results?.find((j) => j.fit_score >= 0.3);
  if (!state.jobs) {
    items.push({
      urgency: 40,
      title: t('todo.resume', 'Add your resume to see job matches'),
      meta: t('todo.resumeMeta', 'You get a fit score and the skills to learn for each job.'),
      action: `<a class="btn btn-secondary btn-sm" href="#/jobs">${esc(t('btn.open', 'Open'))}</a>`,
    });
  } else if (top) {
    const skills = (top.skills_missing || []).slice(0, 3).join(', ');
    items.push({
      urgency: 35,
      title: t('todo.job', 'Look at {title}', { title: top.company ? `${top.title}, ${top.company}` : top.title }),
      meta: skills
        ? t('todo.jobMeta', '{fit}% fit · learn: {skills}', { fit: Math.round(top.fit_score * 100), skills })
        : `${Math.round(top.fit_score * 100)}% ${t('jobs.fit', 'fit')}`,
      action: `<a class="btn btn-secondary btn-sm" href="#/jobs">${esc(t('btn.view', 'View'))}</a>`,
    });
  }

  return items.sort((a, b) => a.urgency - b.urgency).slice(0, 4);
}

function deadlines() {
  const lang = getLang();
  const rows = eligibleMatches()
    .map((m) => ({ m, d: daysLeft(m.deadline) }))
    .filter(({ d }) => d !== null && d >= 0)
    .sort((a, b) => a.d - b.d)
    .slice(0, 5);
  if (!rows.length) return `<p class="quiet small" style="padding:16px 20px">${esc(t('home.noDeadlines', 'None of your eligible schemes has an open deadline.'))}</p>`;
  return `<ol class="timeline">${rows.map(({ m, d }) => `
    <li class="${d <= 7 ? 'urgent' : d <= 30 ? 'soon' : ''}">
      <span class="pin" aria-hidden="true"></span>
      <div>
        <p class="timeline-date num">${esc(fmtDate(m.deadline, lang))} <span class="quiet small">· ${d === 0 ? esc(t('sch.closesToday', 'Closes today')) : `${d} ${lang === 'hi' ? 'दिन' : d === 1 ? 'day' : 'days'}`}</span></p>
        <p class="small">${esc(m.title)}</p>
      </div>
    </li>`).join('')}</ol>`;
}

function readinessBlock() {
  const r = readiness();
  if (!r.total) return '';
  return `<section class="panel panel-pad" aria-labelledby="hRead">
    <div class="section-head" style="margin:0"><h2 class="h3" id="hRead">${esc(t('home.readiness', 'Documents ready'))}</h2>
      <a class="link small" href="#/documents">${esc(t('btn.open', 'Open'))}</a></div>
    <p class="small quiet">${esc(t('home.readyOf', '{have} of {n} documents ready', { have: r.owned, n: r.total }))}</p>
    <div class="meter" style="margin-top:10px" role="img" aria-label="${r.pct}%"><span class="seg-education" style="width:${r.pct}%"></span></div>
    <div class="doc-strip">${r.docs.slice(0, 6).map((d) => `<span class="doc-chip ${hasDoc(d.document) ? 'have' : ''}">${esc(d.document)}</span>`).join('')}
      ${r.total > 6 ? `<a class="doc-chip" href="#/documents">${esc(t('home.more', '+{n} more', { n: r.total - 6 }))}</a>` : ''}</div>
  </section>`;
}

export const home = {
  title: () => t('nav.home', 'Home'),
  deps: ['run', 'running', 'runError', 'profile', 'jobs', 'vault', 'ownedDocs'],
  render(el) {
    const name = state.profile?.name || '';
    if (!state.run) {
      if (state.running) {
        el.innerHTML = `<section class="file-head">
          <p class="working quiet"><span class="spinner"></span>${esc(t('run.working', 'Checking your profile against every scheme…'))}</p>
          <div style="margin-top:24px">${skeleton(5)}</div></section>`;
        return;
      }
      el.innerHTML = state.runError
        ? `<p class="notice notice-bad" role="alert">${icon('triangle-alert')}<span>${esc(state.runError)}</span></p>
           <div class="row" style="margin-top:16px"><button class="btn btn-primary" id="hRun">${icon('refresh-cw')}${esc(t('run.again', 'Check again'))}</button></div>`
        : emptyState({
          title: t('ob.finish', 'Find my matches'),
          action: `<button class="btn btn-primary" id="hRun">${esc(t('ob.finish', 'Find my matches'))}</button>`,
        });
      el.querySelector('#hRun')?.addEventListener('click', () => runAgents().catch(() => {}));
      return;
    }

    const ins = state.run.insights;
    const partial = (state.run.matches || []).filter((m) => matchStatus(m) === 'partial').length;
    const fresh = stampedRunId !== state.run.id;
    stampedRunId = state.run.id;
    const todo = priorities();

    el.innerHTML = `
      ${state.running ? `<p class="notice" role="status"><span class="spinner"></span>${esc(t('run.working', 'Checking your profile against every scheme…'))}</p>` : ''}
      <section class="file-head" aria-labelledby="hVerdict">
        <p class="quiet">${esc(t('home.fileFor', 'File'))}: <strong style="color:var(--ink)">${esc(name)}</strong></p>
        <div class="verdict">
          <h2 class="display" id="hVerdict">${esc(verdictSentence(ins))}</h2>
          ${ins.eligible_count ? stamp('eligible', fresh ? 'stamp-press' : '') : ''}
        </div>
        ${ins.one_time_benefit ? `<p class="lede" style="margin-top:12px">${esc(t('home.oneTime', 'Plus one-time support worth up to {amount}.', { amount: fmtINR(ins.one_time_benefit) }))}</p>` : ''}
        ${partial ? `<p class="lede" style="margin-top:8px"><a class="link" href="#/schemes?filter=partial">${esc(t('home.close', '{n} more are close. See what is missing.', { n: partial }))}</a></p>` : ''}
        ${fileFields()}
      </section>

      <div class="home-grid">
        <section class="panel" aria-labelledby="hTodo">
          <div class="panel-head"><h2 class="h3" id="hTodo">${esc(t('home.todo', 'Do this week'))}</h2></div>
          ${todo.length ? `<ol class="todo">${todo.map((i) => `
            <li><div><p class="todo-title">${esc(i.title)}</p><p class="todo-meta">${esc(i.meta)}</p></div>${i.action}</li>`).join('')}</ol>`
            : `<p class="quiet" style="padding:16px 20px">${esc(t('home.todoEmpty', 'Nothing urgent right now. Check back for new schemes.'))}</p>`}
        </section>
        <div class="stack">
          <section class="panel" aria-labelledby="hDead">
            <div class="panel-head"><h2 class="h3" id="hDead">${esc(t('home.deadlines', 'Coming deadlines'))}</h2></div>
            ${deadlines()}
          </section>
          ${readinessBlock()}
        </div>
      </div>

      <div class="row row-wrap section">
        <button class="btn btn-secondary" id="hRerun" ${state.running ? 'disabled' : ''}>${icon('refresh-cw')}${esc(t('run.again', 'Check again'))}</button>
        <button class="btn btn-quiet" id="hCal">${icon('calendar-plus')}${esc(t('home.calendar', 'Add to calendar'))}</button>
        <button class="btn btn-quiet" id="hPrint">${icon('printer')}${esc(t('home.print', 'Print action plan'))}</button>
      </div>`;

    el.querySelector('#hRerun').addEventListener('click', () => runAgents().catch(() => {}));
    el.querySelector('#hCal').addEventListener('click', downloadCalendar);
    el.querySelector('#hPrint').addEventListener('click', printPlan);
  },
};
