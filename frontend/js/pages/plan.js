/* One job's plan: focus areas, resume fixes and a week-by-week roadmap you can tick off. */
import { esc, store, debounce } from '../util.js';
import { t } from '../i18n.js';
import { icon, toast } from '../ui.js';
import { api } from '../api.js';
import { state, saveJobs } from '../state.js';
import { ring, animateIn } from '../components.js';
import { jobsData, personPayload, sourceStamp, fitColor, meter, hoursField, bindHours, getResume } from './jobs.js';

const KIND_ICON = { learn: 'book-open', build: 'hammer', apply: 'rocket' };
let plan = null;
let job = null;
let loading = false;
let reqId = 0;

const doneKey = (id) => `lp_plan_${id}`;
const doneSteps = (id) => new Set(store.get(doneKey(id), []));

function learnedSkills() {
  const done = doneSteps(job.id);
  return [...new Set(plan.steps.filter((s) => done.has(s.id)).flatMap((s) => s.skills))];
}

async function fetchPlan(hours) {
  const mine = ++reqId;
  const res = await api('/api/opportunities/jobs/plan', {
    method: 'POST',
    json: {
      ...personPayload(),
      job_id: job.source === 'sample' ? job.id : null,
      job: { id: job.id, title: job.title, description: job.description || '', company: job.company, location: job.location, url: job.url, source: job.source },
      hours_per_week: hours,
      learned: plan ? learnedSkills() : [],
    },
  });
  return mine === reqId ? res : null;
}

function journey(p) {
  const pct = (x) => Math.round(x * 100);
  const steps = p.steps.length, done = p.steps.filter((s) => doneSteps(job.id).has(s.id)).length;
  return `
    <div class="journey">
      <div class="j-point"><span class="tiny quiet">${esc(t('plan.today', 'Fit today'))}</span><b class="num">${pct(p.fit_start)}%</b></div>
      <span class="j-arrow">${icon('arrow-right')}</span>
      <div class="j-point j-now">${ring(pct(p.fit_now), { size: 92, stroke: 9, color: fitColor(pct(p.fit_now)), label: `${pct(p.fit_now)}%`, cls: 'fit-ring big' })}
        <span class="tiny quiet">${esc(t('plan.now', 'With what you ticked'))}</span></div>
      <span class="j-arrow">${icon('arrow-right')}</span>
      <div class="j-point"><span class="tiny quiet">${esc(t('plan.after', 'After the plan'))}</span><b class="num" style="color:var(--green)">${pct(p.fit_after)}%</b></div>
    </div>
    <div class="progress-line"><span style="width:${steps ? (100 * done) / steps : 0}%"></span></div>
    <p class="small quiet" style="margin-top:8px">${esc(t('plan.progress', '{d} of {n} steps done · {w} weeks at {h} hrs/week', { d: done, n: steps, w: p.total_weeks, h: p.hours_per_week }))}</p>`;
}

function focusCards(p) {
  const f = p.focus;
  const col = (cls, ic, title, sub, items) => `<section class="card panel-pad focus ${cls}">
    <h2 class="h3">${icon(ic)} ${esc(title)}</h2><p class="tiny quiet">${esc(sub)}</p>
    ${items.length ? `<ul class="focus-list">${items.join('')}</ul>` : `<p class="small quiet" style="margin-top:10px">${esc(t('plan.nothing', 'Nothing here'))}</p>`}</section>`;
  return `<div class="focus-grid">
    ${col('f-have', 'circle-check', t('plan.have', 'You have'), t('plan.haveSub', 'Proved in a job, project or course'),
      f.have.map((x) => `<li><span class="skill">${icon('check', 'icon-sm')}${esc(x.skill)}</span><span class="tiny quiet">${esc(x.evidence === 'work' ? t('ev.work', 'Used at work') : t('ev.project', 'In a project or course'))}</span></li>`))}
    ${col('f-strong', 'gauge', t('plan.strengthen', 'Strengthen'), t('plan.strengthenSub', 'You list these, but nothing shows them yet'),
      f.strengthen.map((x) => `<li><span class="skill weak">${icon('circle-dashed', 'icon-sm')}${esc(x.skill)}</span></li>`))}
    ${col('f-learn', 'book-open', t('plan.learn', 'Learn'), t('plan.learnSub', 'In the order to learn them'),
      f.learn.map((x) => `<li><span class="skill missing ${x.must ? '' : 'nice'}">${esc(x.skill)}</span>
        <span class="tiny quiet">${esc(x.prereq_for ? t('plan.before', 'before {s}', { s: x.prereq_for }) : x.must ? t('plan.must', 'must-have') : t('plan.nice', 'good to have'))} · ${esc(t('plan.wk', '{n} wk', { n: x.weeks }))}${x.demand ? ` · ${esc(t('plan.demand', 'in {a} of {b} similar roles', { a: x.demand.jobs, b: x.demand.of }))}` : ''}</span></li>`))}
  </div>`;
}

function stepItem(s, done) {
  return `<li class="step ${done ? 'done' : ''} step-${esc(s.kind)}" data-step="${esc(s.id)}">
    <div class="step-rail"><span class="step-dot">${icon(done ? 'check' : KIND_ICON[s.kind] || 'flag', 'icon-sm')}</span></div>
    <div class="step-card card">
      <div class="step-top">
        <span class="step-weeks">${esc(s.start_week === s.end_week ? t('plan.week', 'Week {a}', { a: s.start_week }) : t('plan.weeks', 'Weeks {a}–{b}', { a: s.start_week, b: s.end_week }))}</span>
        <label class="tick"><input type="checkbox" data-tick="${esc(s.id)}" ${done ? 'checked' : ''} /><span>${esc(t('plan.done', 'Done'))}</span></label>
      </div>
      <h3 class="h3">${esc(s.title)}</h3>
      <p class="small quiet">${esc(s.why)}</p>
      <ul class="tasks">${s.tasks.map((x) => `<li>${esc(x)}</li>`).join('')}</ul>
      ${s.resources.length ? `<div class="resources">${s.resources.map((r) => /^https:\/\//.test(r.url)
        ? `<a href="${esc(r.url)}" target="_blank" rel="noopener noreferrer"><b>${esc(r.provider)}</b>${esc(r.title)}${icon('external-link', 'icon-sm')}<span class="sr-only"> (opens a new tab)</span></a>` : '').join('')}</div>` : ''}
    </div></li>`;
}

function render(el) {
  if (loading && !plan) {
    el.innerHTML = `<div class="card panel-pad"><p class="working quiet"><span class="spinner"></span>${esc(t('plan.building', 'Building your plan…'))}</p>
      ${[1, 2, 3].map(() => '<div class="skeleton sk-line" style="height:80px;margin:16px 0"></div>').join('')}</div>`;
    return;
  }
  if (!plan) return;
  const p = plan;
  const done = doneSteps(job.id);
  const hasResume = !!getResume().text.trim();
  el.innerHTML = `
    <a class="back-link small" href="#/jobs">${icon('arrow-left', 'icon-sm')}${esc(t('plan.back', 'All matches'))}</a>
    <header class="card plan-hero">
      <div class="plan-hero-main">
        <div class="row row-wrap" style="gap:8px;margin-bottom:10px">${sourceStamp(job)}${p.family_label ? `<span class="tier">${esc(p.family_label)}</span>` : ''}</div>
        <p class="tiny quiet" style="text-transform:uppercase;letter-spacing:.06em;font-weight:700">${esc(t('plan.kicker', 'Your plan for'))}</p>
        <h1 class="h1">${esc(job.title)}</h1>
        ${job.company ? `<p class="quiet">${esc(job.company)}</p>` : ''}
        ${p.unmet.filter((u) => !u.startsWith('Must-have') && !u.startsWith('Listed but')).map((u) => `<p class="small gap" style="margin-top:6px">${icon('triangle-alert', 'icon-sm')} ${esc(u)}</p>`).join('')}
        <div style="margin-top:16px">${meter(p.fit_breakdown)}</div>
        <div class="plan-hours">${hoursField(p.hours_per_week, 'pHours')}</div>
      </div>
      <div class="plan-hero-side" id="pJourney">${journey(p)}</div>
    </header>
    <p class="notice ${hasResume ? '' : 'notice-warn'} plan-basis" style="margin-top:14px">${icon(hasResume ? 'file-search' : 'user-round', 'icon-sm')} ${esc(hasResume
      ? t('plan.basisResume', 'Built from your resume: skills you have proved are skipped, skills you only list are proved in the project.')
      : p.years != null
        ? t('plan.basisForm', 'Built from the job post, the skills you typed and your work experience ({y}). Add your resume on the Jobs page for a sharper plan.', { y: p.years < 1 ? t('exp.fresher', 'fresher') : t('plan.yrs', '{n} yrs', { n: p.years }) })
        : t('plan.noResume', 'This plan only knows the skills you typed. Add your resume or choose your work experience on the Jobs page for a sharper one.'))}</p>
    ${(p.typical_skills || []).length ? `<p class="notice" style="margin-top:10px">${icon('lightbulb', 'icon-sm')} ${esc(t('plan.typical', 'This post names few skills, so the plan adds what {r} roles usually ask for: {s}.', { r: (p.family_label || '').toLowerCase() || t('plan.similar', 'similar'), s: p.typical_skills.join(', ') }))}</p>` : ''}

    <h2 class="h2 section-title">${esc(t('plan.focusT', 'Focus areas'))}</h2>
    ${focusCards(p)}

    ${p.resume_fixes.length ? `<h2 class="h2 section-title">${esc(t('plan.fixesT', 'Fix your resume for this job'))}</h2>
      <section class="card"><ul class="fixes">${p.resume_fixes.map((x) => `<li>${icon('file-pen')}<span>${esc(x)}</span></li>`).join('')}</ul></section>` : ''}

    <div class="row row-wrap section-title" style="justify-content:space-between">
      <h2 class="h2">${esc(t('plan.roadmapT', 'Week-by-week roadmap'))}</h2>
      <button class="btn btn-quiet btn-sm" type="button" id="pPrint">${icon('printer', 'icon-sm')}${esc(t('plan.print', 'Print'))}</button>
    </div>
    <ol class="roadmap">${p.steps.map((s) => stepItem(s, done.has(s.id))).join('')}</ol>`;
  animateIn(el);

  const refit = debounce(async () => {
    try {
      const next = await fetchPlan(plan.hours_per_week);
      if (!next) return;
      plan = next;
      const box = el.querySelector('#pJourney');
      if (box) { box.innerHTML = journey(plan); animateIn(box); }
    } catch (err) { toast(err.message, 'bad'); }
  }, 250);

  el.querySelectorAll('[data-tick]').forEach((c) => c.addEventListener('change', () => {
    const set = doneSteps(job.id);
    c.checked ? set.add(c.dataset.tick) : set.delete(c.dataset.tick);
    store.set(doneKey(job.id), [...set]);
    const li = c.closest('.step');
    li.classList.toggle('done', c.checked);
    const step = plan.steps.find((s) => s.id === c.dataset.tick);
    li.querySelector('.step-dot').innerHTML = icon(c.checked ? 'check' : KIND_ICON[step.kind] || 'flag', 'icon-sm');
    refit();
  }));

  const rebuild = debounce(async (hours) => {
    if (state.jobs) saveJobs({ ...state.jobs, hours });
    try {
      const next = await fetchPlan(hours);
      if (next) { plan = next; const y = scrollY; render(el); scrollTo(0, y); el.querySelector('#pHours')?.focus(); }
    } catch (err) { toast(err.message, 'bad'); }
  }, 400);
  bindHours(el.querySelector('.plan-hours'), rebuild);
  el.querySelector('#pPrint').addEventListener('click', () => {
    document.body.classList.add('print-plan');
    window.print();
    setTimeout(() => document.body.classList.remove('print-plan'), 500);
  });
}

export const jobPlan = {
  title: () => (job ? `${t('plan.kicker', 'Your plan for')} ${job.title}` : t('plan.title', 'Your plan')),
  noHead: true,
  deps: [],
  render(el, params) {
    const id = params.get('id');
    const data = jobsData();
    const found = data?.report.jobs.find((j) => j.id === id);
    if (!found) {
      el.innerHTML = `<div class="card empty"><span class="empty-icon">${icon('route', 'icon-lg')}</span>
        <h2 class="h2">${esc(t('plan.missingT', 'Pick a job first'))}</h2>
        <p class="quiet">${esc(t('plan.missing', 'Find your matches on the Jobs page, then open the plan for one of them.'))}</p>
        <a class="btn btn-primary" href="#/jobs" style="margin-top:14px">${icon('briefcase', 'icon-sm')}${esc(t('nav.jobs', 'Jobs'))}</a></div>`;
      return;
    }
    if (job?.id !== found.id) plan = null;
    job = found;
    window.dispatchEvent(new Event('lp:title'));
    if (plan) { render(el); return; }
    loading = true; render(el);
    fetchPlan(data.hours || 8)
      .then(async (p) => {
        if (!p) return;
        plan = p; loading = false;
        // Ticks saved earlier: score again with those skills counted
        if (doneSteps(job.id).size) { const again = await fetchPlan(p.hours_per_week); if (again) plan = again; }
        render(el);
      })
      .catch((err) => { loading = false; el.innerHTML = `<p class="notice notice-warn">${esc(err.message)}</p>`; });
  },
  leave() { reqId++; },
};
