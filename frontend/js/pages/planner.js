/* Planner: a week-by-week plan of documents, scheme applications, job applications
   and one skill, fitted to the hours you have (0/1 knapsack + earliest deadline first). */
import { esc, fmtDate, daysLeft, debounce } from '../util.js';
import { t, getLang } from '../i18n.js';
import { icon, toast } from '../ui.js';
import { emptyCard } from '../components.js';
import { state } from '../state.js';
import { priorityPlan, planHours } from '../features.js';

const KIND = {
  document: ['file-text', 'pp.kDoc', 'Document'],
  scheme: ['landmark', 'pp.kScheme', 'Scheme'],
  job: ['briefcase', 'pp.kJob', 'Job'],
  skill: ['graduation-cap', 'pp.kSkill', 'Skill'],
};
const PRESETS = [3, 6, 10, 15, 20];

export function taskRow(task) {
  const [ic, k, en] = KIND[task.kind] || KIND.document;
  const lang = getLang();
  const d = daysLeft(task.deadline);
  const meta = [
    `${task.hours} ${t('pp.h', 'h')}`,
    task.deadline ? t('pp.closes', 'closes {date}', { date: fmtDate(task.deadline, lang) }) : '',
    task.fit ? t('pp.fit', '{p}% fit', { p: Math.round(task.fit * 100) }) : '',
    task.amount || '',
  ].filter(Boolean).join(' · ');
  return `<li class="ptask ${task.at_risk ? 'risk' : ''}">
    <span class="ptask-icon k-${esc(task.kind)}" title="${esc(t(k, en))}">${icon(ic, 'icon-sm')}</span>
    <div style="min-width:0">
      <p class="todo-title">${esc(task.title)}${task.partial ? ` <span class="quiet small">(${esc(t('pp.partial', 'part of it'))})</span>` : ''}</p>
      <p class="todo-meta">${esc(meta)}</p>
      ${task.why ? `<p class="tiny quiet">${esc(task.why)}</p>` : ''}
      ${task.at_risk ? `<p class="tiny bad">${icon('triangle-alert', 'icon-sm')} ${esc(d !== null && d <= 3 ? t('pp.riskSoon', 'Closes in {d} days: do this first', { d: Math.max(0, d) }) : t('pp.risk', 'Closes early in this week: start now'))}</p>` : ''}
    </div>
    ${task.url ? `<a class="btn btn-quiet btn-sm" href="${esc(task.url)}" target="_blank" rel="noopener noreferrer">${esc(t('btn.open', 'Open'))}${icon('external-link', 'icon-sm')}<span class="sr-only"> (opens a new tab)</span></a>`
      : task.kind === 'document' ? `<a class="btn btn-quiet btn-sm" href="#/documents">${esc(t('btn.view', 'View'))}</a>` : '<span></span>'}
  </li>`;
}

function weekCard(w, lang) {
  return `<section class="card week">
    <div class="panel-head"><h2 class="h3">${esc(t('pp.week', 'Week {n}', { n: w.week }))} <span class="quiet small">${esc(fmtDate(w.start, lang))} – ${esc(fmtDate(w.end, lang))}</span></h2>
      <span class="tiny quiet num">${esc(t('pp.used', '{h} h planned', { h: w.hours_used }))}</span></div>
    <ul class="ptasks">${w.tasks.map(taskRow).join('')}</ul></section>`;
}

function summary(res) {
  const tt = res.totals;
  const gain = tt.naive_value ? Math.round(((tt.value - tt.naive_value) / tt.naive_value) * 100) : 0;
  return `<div class="figures">
    <div class="card figure"><p class="figure-value num">${tt.tasks}</p><p class="figure-label">${esc(t('pp.fTasks', 'Tasks: {d} documents, {s} schemes, {j} jobs', { d: tt.documents, s: tt.schemes, j: tt.jobs }))}</p></div>
    <div class="card figure"><p class="figure-value num">${res.weeks.length}</p><p class="figure-label">${esc(t('pp.fWeeks', 'Weeks at {h} hours a week', { h: res.hours_per_week }))}</p></div>
    <div class="card figure"><p class="figure-value num ${tt.at_risk ? 'bad' : ''}">${tt.at_risk + res.missed.length}</p><p class="figure-label">${esc(t('pp.fRisk', 'At risk or missed'))}</p></div>
  </div>
  <p class="small quiet" style="margin-top:10px">${icon('gauge', 'icon-sm')} ${esc(t('pp.compare', 'Priority points captured on time: this plan {a}, nearest-deadline-first {b}', { a: tt.value, b: tt.naive_value }))}${gain > 0 ? ` <strong class="ok">(+${gain}%)</strong>` : ''}</p>`;
}

export const planner = {
  title: () => t('pp.title', 'Your plan'),
  sub: () => t('pp.sub', 'What to do each week, fitted to the time you have. Documents first when they unlock the most.'),
  deps: ['run', 'vault', 'ownedDocs', 'jobs'],
  async render(el) {
    if (!state.run) {
      el.innerHTML = emptyCard({ iconName: 'list-todo', title: t('sch.noRun', 'Fill in your profile first to see schemes.'), action: `<a class="btn btn-primary" href="#/start">${esc(t('land.start', 'Get started free'))}</a>` });
      return;
    }
    const hours = planHours.get();
    el.innerHTML = `
      <section class="card panel-pad">
        <label class="label" for="pHours">${esc(t('pp.hours', 'Hours you can give each week'))}: <strong class="num" id="pHoursV">${hours}</strong></label>
        <input class="range" type="range" id="pHours" min="1" max="40" step="1" value="${hours}" style="--pct:${((hours - 1) / 39) * 100}%" />
        <div class="presets">${PRESETS.map((h) => `<button type="button" class="preset" data-h="${h}">${h} ${esc(t('pp.h', 'h'))}</button>`).join('')}</div>
        ${!state.jobs ? `<p class="tiny quiet" style="margin-top:8px">${esc(t('pp.noJobs', 'Search on the Jobs page to add job applications and a skill to this plan.'))} <a class="link" href="#/jobs">${esc(t('nav.jobs', 'Jobs'))}</a></p>` : ''}
      </section>
      <div id="pBody" class="section"></div>
      <details class="section card panel-pad"><summary class="h3" style="cursor:pointer">${esc(t('pp.howT', 'How this plan is made'))}</summary>
        <ul class="facts-list small" style="margin-top:10px">
          <li>${esc(t('pp.how1', 'Each task has hours and a value. A scheme is worth more the bigger its amount; a job is worth its fit score.'))}</li>
          <li>${esc(t('pp.how2', 'A document has no value of its own: it carries the value of the applications it unblocks, so one needed by many schemes comes first.'))}</li>
          <li>${esc(t('pp.how3', 'Each week, the set of ready tasks that fits your hours with the most value is picked (0/1 knapsack). Things closing within two weeks count double.'))}</li>
          <li>${esc(t('pp.how4', 'Ties go to the earliest deadline. The same tasks are also planned nearest-deadline-first, to compare.'))}</li>
        </ul></details>`;

    const body = el.querySelector('#pBody');
    const draw = async (h) => {
      body.innerHTML = `<p class="working quiet"><span class="spinner"></span>${esc(t('pp.loading', 'Planning your weeks…'))}</p>`;
      let res;
      try { res = await priorityPlan(h); } catch (err) { body.innerHTML = ''; toast(err.message, 'bad'); return; }
      if (!body.isConnected) return;
      const lang = getLang();
      body.innerHTML = `${summary(res)}
        ${res.weeks.length ? `<div class="stack" style="margin-top:16px">${res.weeks.map((w) => weekCard(w, lang)).join('')}</div>`
          : `<div class="card"><p class="quiet" style="padding:22px">${esc(t('pp.empty', 'Nothing to plan: you have every document and no open application is waiting.'))}</p></div>`}
        ${res.missed.length ? `<section class="card section"><div class="panel-head"><h2 class="h3 bad">${esc(t('pp.missed', 'Will close before you get to them'))}</h2></div>
          <ul class="ptasks">${res.missed.map(taskRow).join('')}</ul>
          <p class="tiny quiet" style="padding:0 22px 16px">${esc(t('pp.missedP', 'Give more hours a week, or do these first and push other tasks later.'))}</p></section>` : ''}
        ${res.not_scheduled.length ? `<details class="section"><summary class="h3" style="cursor:pointer">${esc(t('pp.later', 'After these {n} weeks', { n: res.weeks.length }))} <span class="quiet num">(${res.not_scheduled.length})</span></summary>
          <section class="card" style="margin-top:10px"><ul class="ptasks">${res.not_scheduled.map(taskRow).join('')}</ul></section></details>` : ''}`;
    };
    const slider = el.querySelector('#pHours');
    const later = debounce((h) => draw(h), 300);
    const set = (h) => {
      slider.value = h; slider.style.setProperty('--pct', `${((h - 1) / 39) * 100}%`);
      el.querySelector('#pHoursV').textContent = h;
      planHours.set(h); later(h);
    };
    slider.addEventListener('input', () => set(+slider.value));
    el.querySelectorAll('[data-h]').forEach((b) => b.addEventListener('click', () => set(+b.dataset.h)));
    draw(hours);
  },
};

/** Home card: this week's tasks. */
export async function thisWeek(box) {
  if (!box || !state.profileId) return;
  try {
    const res = await priorityPlan();
    if (!box.isConnected) return;
    const w = res.weeks[0];
    box.innerHTML = w
      ? `<ul class="ptasks">${w.tasks.slice(0, 4).map(taskRow).join('')}</ul>
         <p class="tiny quiet" style="padding:0 22px 14px">${esc(t('pp.homeNote', '{h} hours a week · {n} weeks planned', { h: res.hours_per_week, n: res.weeks.length }))}</p>`
      : `<p class="quiet small" style="padding:18px 22px">${esc(t('pp.empty', 'Nothing to plan: you have every document and no open application is waiting.'))}</p>`;
  } catch {
    box.innerHTML = '';
  }
}
