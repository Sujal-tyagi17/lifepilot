/* Home: your file. One sentence verdict, what to do this week, deadlines, documents. */
import { esc, fmtINR, daysLeft, fmtDate, matchStatus } from '../util.js';
import { t, getLang } from '../i18n.js';
import { icon, stamp, skeleton } from '../ui.js';
import { emptyCard, ring, animateIn } from '../components.js';
import { state, eligibleMatches, readiness, hasDoc } from '../state.js';
import { runAgents } from '../run.js';
import { downloadCalendar, printPlan } from '../print.js';
import { EDUCATION } from '../profileFields.js';
import { thisWeek } from './planner.js';

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
    ['f.education', 'Education', edu ? (getLang() === 'hi' ? edu[2] : edu[1]) : null, 'graduation-cap'],
    ['f.category', 'Category', p.category, 'users'],
    ['f.state', 'State', p.state, 'map-pin'],
    ['f.income', 'Family income per year (₹)', p.annual_income != null ? fmtINR(p.annual_income) : null, 'wallet'],
  ];
  return `<div class="profile-chips">${fields.map(([k, en, v, ic]) => v
    ? `<a class="pchip" href="#/profile" title="${esc(t(k, en).replace(' (₹)', ''))}">${icon(ic, 'icon-sm')}${esc(v)}</a>`
    : `<a class="pchip blank" href="#/profile">${icon('plus', 'icon-sm')}${esc(t('home.addField', 'Add {field}', { field: t(k, en).replace(' (₹)', '').toLowerCase() }))}</a>`).join('')}</div>`;
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

  const top = (state.jobs?.report?.jobs || []).find((j) => j.fit_score >= 0.3 && j.source !== 'sample');
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
  return `<section class="card panel-pad" aria-labelledby="hRead">
    <div class="row" style="gap:18px;align-items:center">
      ${ring(r.pct, { size: 96, stroke: 9, label: `${r.pct}%` })}
      <div style="min-width:0"><h2 class="h3" id="hRead">${esc(t('home.readiness', 'Documents ready'))}</h2>
        <p class="small quiet">${esc(t('home.readyOf', '{have} of {n} documents ready', { have: r.owned, n: r.total }))}</p>
        <a class="link small" href="#/documents" style="display:inline-block;margin-top:6px">${esc(t('home.manageDocs', 'Manage documents'))}</a></div>
    </div>
    <div class="doc-strip">${r.docs.slice(0, 6).map((d) => `<span class="doc-chip ${hasDoc(d.document) ? 'have' : ''}">${esc(d.document)}</span>`).join('')}
      ${r.total > 6 ? `<a class="doc-chip" href="#/documents">${esc(t('home.more', '+{n} more', { n: r.total - 6 }))}</a>` : ''}</div>
  </section>`;
}

export const home = {
  title: () => t('nav.home', 'Home'),
  noHead: true,
  deps: ['run', 'running', 'runError', 'profile', 'jobs', 'vault', 'ownedDocs'],
  render(el) {
    const name = (state.profile?.name || '').split(' ')[0];
    if (!state.run) {
      if (state.running) {
        el.innerHTML = `<div class="card hello"><div><p class="working quiet"><span class="spinner"></span>${esc(t('run.working', 'Checking your profile against every scheme…'))}</p>
          <div style="margin-top:18px">${skeleton(4)}</div></div></div>`;
        return;
      }
      el.innerHTML = state.runError
        ? `<p class="notice notice-bad" role="alert">${icon('triangle-alert')}<span>${esc(state.runError)}</span></p>
           <div class="row" style="margin-top:16px"><button class="btn btn-primary" id="hRun">${icon('refresh-cw')}${esc(t('run.again', 'Check again'))}</button></div>`
        : emptyCard({ title: t('home.noRun', 'Let’s find your matches'), body: t('home.noRunP', 'Run a check against every scheme with your saved profile.'),
          action: `<button class="btn btn-primary" id="hRun">${icon('sparkles')}${esc(t('ob.finish', 'Find my matches'))}</button>` });
      el.querySelector('#hRun')?.addEventListener('click', () => runAgents().catch(() => {}));
      return;
    }

    const ins = state.run.insights;
    const partial = (state.run.matches || []).filter((m) => matchStatus(m) === 'partial').length;
    const fresh = stampedRunId !== state.run.id;
    stampedRunId = state.run.id;
    const todo = priorities();
    const r = readiness();
    const nextDeadline = eligibleMatches().map((m) => daysLeft(m.deadline)).filter((d) => d !== null && d >= 0).sort((a, b) => a - b)[0];

    el.innerHTML = `
      ${state.running ? `<p class="notice" role="status" style="margin-bottom:14px"><span class="spinner"></span>${esc(t('run.working', 'Checking your profile against every scheme…'))}</p>` : ''}
      <section class="card hello" aria-labelledby="hVerdict">
        <div>
          <p class="quiet">${esc(t('home.hi', 'Hi {name}, here is your file', { name }))}</p>
          <h1 class="display" id="hVerdict" style="margin-top:8px">${esc(verdictSentence(ins))}</h1>
          ${ins.one_time_benefit ? `<p class="lede" style="margin-top:10px">${esc(t('home.oneTime', 'Plus one-time support worth up to {amount}.', { amount: fmtINR(ins.one_time_benefit) }))}</p>` : ''}
          ${partial ? `<p style="margin-top:10px"><a class="link" href="#/schemes?filter=partial">${esc(t('home.close', '{n} more are close. See what is missing.', { n: partial }))}</a></p>` : ''}
          ${fileFields()}
        </div>
        <div class="verdict-stamp">${ins.eligible_count ? stamp('eligible', fresh ? 'stamp-press' : '') : stamp('partial')}</div>
      </section>

      <div class="stats">
        <div class="card stat"><span class="stat-accent" style="background:var(--green)"></span><p class="stat-value num" data-count="${ins.eligible_count}">0</p><p class="stat-label">${esc(t('home.statElig', 'Schemes you qualify for'))}</p></div>
        <div class="card stat"><span class="stat-accent" style="background:var(--saffron)"></span><p class="stat-value num" data-count="${ins.estimated_annual_benefit}" data-money="1">₹0</p><p class="stat-label">${esc(t('home.statYear', 'Worth each year'))}</p></div>
        <div class="card stat"><span class="stat-accent" style="background:var(--red)"></span><p class="stat-value num">${nextDeadline !== undefined ? `<span data-count="${nextDeadline}">0</span><span class="small quiet"> ${esc(t('home.days', 'days'))}</span>` : '–'}</p><p class="stat-label">${esc(t('home.statNext', 'Until the next deadline'))}</p></div>
        <div class="card stat"><span class="stat-accent" style="background:var(--indigo)"></span><p class="stat-value num"><span data-count="${r.owned}">0</span><span class="small quiet"> / ${r.total}</span></p><p class="stat-label">${esc(t('home.statDocs', 'Documents ready'))}</p></div>
      </div>

      <div class="home-grid">
        <section class="card" aria-labelledby="hTodo">
          <div class="panel-head"><h2 class="h3" id="hTodo">${esc(t('home.todo', 'Do this week'))}</h2>
            <div class="row" style="gap:4px"><a class="btn btn-quiet btn-sm" href="#/planner">${icon('list-todo', 'icon-sm')}${esc(t('pp.full', 'Full plan'))}</a>
            <button class="btn btn-quiet btn-sm" id="hRerun" ${state.running ? 'disabled' : ''}>${icon('refresh-cw', 'icon-sm')}${esc(t('run.again', 'Check again'))}</button></div></div>
          <div id="hWeek">${todo.length ? `<ol class="todo">${todo.map((i) => `
            <li><div><p class="todo-title">${esc(i.title)}</p><p class="todo-meta">${esc(i.meta)}</p></div>${i.action}</li>`).join('')}</ol>`
            : `<p class="quiet" style="padding:18px 22px">${esc(t('home.todoEmpty', 'Nothing urgent right now. Check back for new schemes.'))}</p>`}</div>
        </section>
        <div class="stack" style="margin-top:0">
          <section class="card" aria-labelledby="hDead">
            <div class="panel-head"><h2 class="h3" id="hDead">${esc(t('home.deadlines', 'Coming deadlines'))}</h2>
              <button class="btn btn-quiet btn-sm" id="hCal" title="${esc(t('home.calendar', 'Add to calendar'))}">${icon('calendar-plus', 'icon-sm')}<span class="sr-only">${esc(t('home.calendar', 'Add to calendar'))}</span></button></div>
            ${deadlines()}
          </section>
          ${readinessBlock()}
        </div>
      </div>
      <div class="row row-wrap section">
        <button class="btn btn-quiet" id="hPrint">${icon('printer')}${esc(t('home.print', 'Print action plan'))}</button>
        <button class="btn btn-quiet" data-assistant>${icon('message-circle')}${esc(t('cmd.asst', 'Ask the assistant'))}</button>
      </div>`;

    el.querySelector('#hRerun').addEventListener('click', () => runAgents().catch(() => {}));
    thisWeek(el.querySelector('#hWeek'));   // the planner's first week replaces the quick list when it is ready
    el.querySelector('#hCal').addEventListener('click', downloadCalendar);
    el.querySelector('#hPrint').addEventListener('click', printPlan);
    if (fresh) {
      animateIn(el);   // count up numbers and fill the ring once per new result
    } else {
      el.querySelectorAll('[data-count]').forEach((n) => { n.textContent = n.dataset.money === '1' ? fmtINR(+n.dataset.count) : (+n.dataset.count).toLocaleString('en-IN'); });
      el.querySelectorAll('circle[data-offset]').forEach((c) => { c.style.transition = 'none'; c.style.strokeDashoffset = c.dataset.offset; });
    }
  },
};
