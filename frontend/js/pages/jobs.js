/* Jobs: profile + resume + target role in; ranked jobs, what we read, and a plan per job out. */
import { esc } from '../util.js';
import { t } from '../i18n.js';
import { icon, toast } from '../ui.js';
import { api } from '../api.js';
import { state, saveJobs } from '../state.js';
import { tagInput, bindControls, ring, animateIn } from '../components.js';

export const SEGMENTS = [
  ['must', 'seg.must', 'Must-have skills'], ['nice', 'seg.nice', 'Good to have'], ['role', 'seg.role', 'Role'],
  ['experience', 'seg.experience', 'Experience'], ['education', 'seg.education', 'Education'],
  ['field', 'seg.field', 'Field'], ['text', 'seg.text', 'Resume wording'],
];
const ROLES = ['Data analyst', 'Backend developer', 'Frontend developer', 'Accountant', 'Sales executive', 'Teacher', 'Graphic designer'];
const SKILL_IDEAS = ['Python', 'SQL', 'Excel', 'Java', 'React', 'Communication', 'Tally'];
export const EVIDENCE = {
  work: ['ev.work', 'Used at work'], project: ['ev.project', 'In a project or course'],
  listed: ['ev.listed', 'Only listed'], form: ['ev.form', 'Typed by you'],
};

/* The resume stays in this browser tab only (sessionStorage), never on the server or in localStorage. */
export function getResume() {
  try { return JSON.parse(sessionStorage.getItem('lp_resume')) || { text: '', file: '' }; } catch { return { text: '', file: '' }; }
}
function setResume(r) { try { sessionStorage.setItem('lp_resume', JSON.stringify(r)); } catch { /* private mode */ } }

/** Saved search, or null for nothing yet (or the old format from before Phase 2). */
export function jobsData() { return state.jobs?.report ? state.jobs : null; }

/** What the matcher and planner need to know about the person. */
export function personPayload() {
  const d = state.jobs || {};
  return { profile: state.profile || {}, resume_text: getResume().text, desired_role: d.role || '', skills: d.skills || [] };
}

let resume = getResume();
let showPaste = false;
let placeFilter = 'all';
let showWeak = false;
let showSamples = false;
let busy = false;

/** Where the job came from, so example roles never pass for real openings. */
export function sourceStamp(j) {
  if (j.source === 'sample') return `<span class="stamp stamp-sample" title="${esc(t('jobs.sampleNote', 'Example role, not a live opening. Check the company careers page.'))}">${esc(t('st.sample', 'Sample'))}</span>`;
  if (j.source === 'web_search') return `<span class="stamp stamp-web" title="${esc(t('jobs.webNote', 'A web search result page, not a single job posting. Open it to find openings.'))}">${esc(t('st.web', 'Search result'))}</span>`;
  const site = j.site || ({ adzuna: 'Adzuna', jooble: 'Jooble', rss: 'RSS' })[j.source] || '';
  const tip = j.source === 'web_job' ? t('jobs.webJobNote', 'Found through Google. Open it to check it is still open.') : '';
  return `<span class="stamp stamp-live" ${tip ? `title="${esc(tip)}"` : ''}>${esc(t('st.live', 'Live'))}${site ? ` · ${esc(site)}` : ''}</span>`;
}

function placeTag(j) {
  const where = j.location && j.location !== 'India' ? j.location : '';
  if (j.location_tag === 'near') return `<span class="place near">${icon('map-pin', 'icon-sm')}${esc(where || t('jobs.near', 'Your state'))}</span>`;
  if (j.location_tag === 'remote') return `<span class="place">${icon('map-pin', 'icon-sm')}${esc(t('jobs.remote', 'Remote'))}</span>`;
  return where ? `<span class="place">${icon('map-pin', 'icon-sm')}${esc(where)}</span>` : '';
}

export function fitColor(fit) { return fit >= 70 ? 'var(--green)' : fit >= 50 ? 'var(--saffron)' : 'var(--ink-3)'; }
const tierLabel = (tier) => ({ strong: t('tier.strong', 'Strong fit'), good: t('tier.good', 'Good fit'), stretch: t('tier.stretch', 'Stretch') })[tier] || '';

export function meter(breakdown) {
  const parts = (breakdown || []).filter((b) => b.points > 0);
  if (!parts.length) return '';
  return `<div class="meter" role="img" aria-label="${esc(t('jobs.breakdown', 'How the score is made'))}: ${esc(parts.map((b) => `${t(`seg.${b.signal}`, b.signal)} ${Math.round(b.points)}`).join(', '))}">
    ${parts.map((b) => `<span class="seg-${esc(b.signal)}" style="width:0" data-width="${b.points}%" title="${esc(t(`seg.${b.signal}`, b.signal))}: ${Math.round(b.points)}"></span>`).join('')}</div>`;
}

function jobItem(j) {
  const fit = Math.round((j.fit_score || 0) * 100);
  const url = j.url && /^https?:/.test(j.url) ? j.url : null;
  const weak = new Set(j.skills_weak || []);
  const alts = j.alternatives || {};
  const notes = (j.unmet || []).filter((u) => !u.startsWith('Must-have skills') && !u.startsWith('Listed but'));
  return `<li class="job">
    <div class="job-head">
      <div style="min-width:0">
        <div class="row row-wrap" style="gap:8px;margin-bottom:8px">${sourceStamp(j)}
          <span class="tier tier-${esc(j.tier)}">${esc(tierLabel(j.tier))}</span>
          ${j.eligible ? '' : `<span class="stamp stamp-partial">${esc(t('jobs.eduGap', 'Education gap'))}</span>`}</div>
        <h3 class="h3">${esc(j.title)}</h3>
        <p class="small quiet">${esc([j.company, j.family_label].filter(Boolean).join(' · '))}</p>
        <div class="row row-wrap" style="gap:6px;margin-top:6px">${placeTag(j)}${j.posted ? `<span class="place">${icon('clock', 'icon-sm')}${esc(j.posted)}</span>` : ''}</div>
        <p class="small" style="margin-top:4px">${icon('wallet', 'icon-sm')} ${esc(j.salary === 'Not disclosed' ? t('jobs.notDisclosed', 'Salary not disclosed') : j.salary)}</p>
      </div>
      ${ring(fit, { size: 68, stroke: 7, color: fitColor(fit), label: `${fit}%`, cls: 'fit-ring' })}
    </div>
    <div style="margin-top:14px">${meter(j.fit_breakdown)}</div>
    <div class="skills">
      ${(j.skills_matched || []).map((s) => weak.has(s)
        ? `<span class="skill weak" title="${esc(t('jobs.weakT', 'You list it, but no project or job shows it'))}">${icon('circle-dashed', 'icon-sm')}${esc(s)}</span>`
        : `<span class="skill" title="${esc(t('jobs.have', 'You have'))}">${icon('check', 'icon-sm')}${esc(s)}</span>`).join('')}
      ${(j.skills_missing || []).map((s) => `<span class="skill missing" title="${esc(t('jobs.mustT', 'Must-have to learn'))}">${esc([s, ...(alts[s] || [])].join(' / '))}</span>`).join('')}
      ${(j.skills_missing_nice || []).map((s) => `<span class="skill missing nice" title="${esc(t('jobs.niceT', 'Good to have'))}">${esc(s)}</span>`).join('')}
    </div>
    ${notes.map((u) => `<p class="small gap" style="margin-top:8px">${esc(u)}</p>`).join('')}
    <div class="row row-wrap" style="margin-top:14px;gap:8px">
      <a class="btn btn-primary btn-sm" href="#/jobs/plan?id=${encodeURIComponent(j.id)}">${icon('route', 'icon-sm')}${esc(t('jobs.plan', 'See my plan'))}</a>
      ${url ? `<a class="btn btn-secondary btn-sm" href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(j.source === 'web_search' ? t('jobs.openSearch', 'Open search results') : j.site ? t('jobs.openOn', 'Open on {s}', { s: j.site }) : t('jobs.applyAt', 'See it on the company site'))}${icon('external-link', 'icon-sm')}<span class="sr-only"> (opens a new tab)</span></a>` : ''}
    </div>
  </li>`;
}

function readCard(rep) {
  const r = rep.resume || {};
  const target = rep.target_label
    ? `<p class="small">${icon('target', 'icon-sm')} ${esc(t('jobs.lookingFor', 'Looking for'))}: <strong>${esc(rep.target_label)}</strong>
        <span class="quiet">(${esc(rep.target_from === 'resume' ? t('jobs.fromResume', 'from your resume') : t('jobs.fromRole', 'from the role you typed'))})</span></p>` : '';
  if (!r.has_resume) {
    return `<section class="card panel-pad read-card">
      <h2 class="h3">${icon('file-search')} ${esc(t('jobs.readT', 'What we read from your resume'))}</h2>
      <p class="notice notice-warn" style="margin-top:10px">${esc(t('jobs.noResume', 'No resume added, so we only know the skills you typed. Add it to see which skills you have proved and get a sharper plan.'))}</p>
      ${target}</section>`;
  }
  const facts = [
    r.degree ? [icon('graduation-cap', 'icon-sm'), r.degree.label] : null,
    [icon('briefcase', 'icon-sm'), r.years ? t('jobs.years', '{n} years of work', { n: r.years }) : t('jobs.noYears', 'No full-time work yet')],
    r.internships ? [icon('badge-check', 'icon-sm'), t('jobs.interns', '{n} internship(s)', { n: r.internships })] : null,
    [icon('layers', 'icon-sm'), t('jobs.sections', '{n} sections', { n: (r.sections || []).length })],
  ].filter(Boolean);
  const groups = ['work', 'project', 'listed'].map((ev) => [ev, (r.skills || []).filter((s) => s.evidence === ev && s.where !== 'form')]);
  const typed = (r.typed_only || []);
  return `<section class="card panel-pad read-card">
    <h2 class="h3">${icon('file-search')} ${esc(t('jobs.readT', 'What we read from your resume'))}</h2>
    <div class="facts">${facts.map(([ic, txt]) => `<span>${ic}${esc(txt)}</span>`).join('')}</div>
    ${target}
    <div class="ev-groups">
      ${groups.filter(([, list]) => list.length).map(([ev, list]) => `<div><p class="tiny quiet ev-label"><i class="ev-dot ev-${ev}"></i>${esc(t(...EVIDENCE[ev]))}</p>
        <div class="skills" style="margin-top:6px">${list.map((s) => `<span class="skill ev ev-${ev}" title="${esc(s.where.startsWith('via') ? s.where : t('jobs.foundIn', 'Found in {s}', { s: s.where }))}">${esc(s.name)}</span>`).join('')}</div></div>`).join('')}
      ${typed.length ? `<div><p class="tiny quiet ev-label"><i class="ev-dot ev-form"></i>${esc(t(...EVIDENCE.form))}</p>
        <div class="skills" style="margin-top:6px">${typed.map((s) => `<span class="skill ev ev-form">${esc(s)}</span>`).join('')}</div></div>` : ''}
    </div></section>`;
}

function insightCard(ins) {
  if (!ins) return '';
  const before = Math.round(ins.fit_before * 100), after = Math.round(ins.fit_after * 100);
  return `<section class="card panel-pad insight">
    <span class="insight-icon">${icon('lightbulb')}</span>
    <div>
      <p class="tiny quiet" style="text-transform:uppercase;letter-spacing:.06em;font-weight:700">${esc(t('jobs.insightK', 'Best next skill'))}</p>
      <h2 class="h3">${esc(t('jobs.insightT', 'Learn {s} next', { s: ins.skill }))}</h2>
      <p class="small">${esc(t('jobs.insight', 'Asked by {n} of your top {of} matches. Their fit goes from {a}% to {b}%. About {w} weeks at 8 hours a week.', { n: ins.jobs, of: ins.of, a: before, b: after, w: ins.weeks }))}</p>
      <div class="lift"><span class="num">${before}%</span><span class="lift-bar"><i style="width:${before}%"></i><b style="left:${before}%;width:0" data-width="${Math.max(0, after - before)}%"></b></span><span class="num" style="color:var(--green)">${after}%</span></div>
      ${(ins.also || []).length ? `<p class="tiny quiet" style="margin-top:6px">${esc(t('jobs.insightAlso', 'Also common in your matches'))}: ${esc(ins.also.join(', '))}</p>` : ''}
    </div></section>`;
}

function results(el) {
  const box = el.querySelector('#jResults');
  const data = jobsData();
  if (busy) {
    box.innerHTML = `<div class="card panel-pad"><p class="working quiet"><span class="spinner"></span>${esc(t('jobs.finding', 'Reading your resume and scoring every job…'))}</p>
      ${[1, 2, 3].map(() => '<div class="skeleton sk-line" style="height:90px;margin:16px 0"></div>').join('')}</div>`;
    return;
  }
  if (!data) {
    box.innerHTML = `<div class="card empty"><span class="empty-icon">${icon('briefcase', 'icon-lg')}</span>
      <h2 class="h2">${esc(t('jobs.emptyT', 'Your matches will appear here'))}</h2>
      <p class="quiet">${esc(t('jobs.empty', 'Add your resume and the role you want. We read what you have proved, score every job, and build a plan for the one you pick.'))}</p></div>`;
    return;
  }
  const rep = data.report;
  const q = (el.querySelector('#jFilter')?.value || '').toLowerCase();
  const items = rep.jobs.filter((j) => {
    if (placeFilter === 'near' && j.location_tag !== 'near') return false;
    if (placeFilter === 'remote' && j.location_tag !== 'remote') return false;
    return !q || `${j.title} ${j.company || ''} ${j.location || ''} ${j.family_label || ''}`.toLowerCase().includes(q);
  });
  const live = items.filter((j) => j.source !== 'sample');
  const samples = items.filter((j) => j.source === 'sample' && j.relevant);
  const by = (g) => live.filter((j) => j.group === g);
  const target = by('target'), other = by('other'), weak = by('weak');
  const list = (arr) => `<section class="card"><ul class="rows">${arr.map(jobItem).join('')}</ul></section>`;
  const head = (txt, n) => `<h2 class="h3 group-head">${esc(txt)} <span class="count">${n}</span></h2>`;
  const noLive = !target.length && !other.length;
  const samplesOpen = showSamples;
  const status = rep.source_status || [];
  const failed = status.filter((x) => x.message.startsWith('failed'));
  const places = [['all', t('jobs.allIndia', 'All India')], ...(rep.state ? [['near', rep.state]] : []), ['remote', t('jobs.remote', 'Remote')]];

  box.innerHTML = `
    ${readCard(rep)}
    ${insightCard(rep.insight)}
    ${!(rep.sources || []).length ? `<p class="notice notice-warn" style="margin-top:14px">${icon('wifi-off', 'icon-sm')} ${esc(t('jobs.noLiveSrc', 'Live job search is not set up on this server, so only example roles are shown. Add SERPER_API_KEY (free at serper.dev) or SERPAPI_KEY (free at serpapi.com) to backend/.env and restart to see real openings.'))}</p>` : ''}
    <div class="toolbar" style="margin-top:18px">
      <label class="input-icon"><span class="sr-only">${esc(t('jobs.filterPh', 'Filter by title or company'))}</span>${icon('search')}<input class="input" type="search" id="jFilter" value="${esc(q)}" placeholder="${esc(t('jobs.filterPh', 'Filter by title or company'))}" /></label>
      <div class="segmented" role="group" aria-label="${esc(t('jobs.where', 'Where'))}">
        ${places.map(([k, label]) => `<button type="button" data-place="${k}" aria-pressed="${placeFilter === k}">${esc(label)}</button>`).join('')}
      </div>
    </div>
    <div class="legend" aria-hidden="true" style="margin-bottom:12px">${SEGMENTS.map(([k, key, en]) => `<span><i class="seg-${k}"></i>${esc(t(key, en))}</span>`).join('')}</div>
    ${status.length ? `<p class="${failed.length ? 'notice notice-warn' : 'tiny quiet'} search-status" style="margin:0 0 8px">${icon(failed.length ? 'triangle-alert' : 'search', 'icon-sm')} ${esc(t('jobs.searched', 'Searched'))}: ${status.map((x) => `<span>${esc(x.source)} — ${esc(x.message)}</span>`).join(' · ')}</p>` : ''}
    ${rep.state && !noLive ? `<p class="tiny quiet" style="margin-bottom:4px">${esc(t('jobs.orderNote', 'Jobs in {s} first, then remote, then the rest of India.', { s: rep.state }))}</p>` : ''}
    ${target.length ? head(rep.target_from === 'resume' ? t('jobs.gResume', 'Best for your resume') : t('jobs.gTarget', 'Roles you asked for'), target.length) + list(target) : ''}
    ${other.length ? head(target.length ? t('jobs.gOther', 'Also fits your resume') : t('jobs.gMatches', 'Your matches'), other.length) + list(other) : ''}
    ${noLive && (rep.sources || []).length ? `<div class="card"><p class="quiet" style="padding:22px">${esc(t('jobs.noLive2', 'No live openings matched this search right now. Try a shorter role name (for example "Data analyst"), or check the search status above.'))}</p></div>` : ''}
    ${weak.length ? `<div class="row" style="justify-content:center;margin-top:16px"><button class="btn btn-quiet btn-sm" type="button" id="jWeak" aria-expanded="${showWeak}">
        ${icon(showWeak ? 'chevron-up' : 'chevron-down', 'icon-sm')}${esc(showWeak ? t('jobs.hideWeak', 'Hide weaker matches') : t('jobs.showWeak', 'Show {n} weaker matches', { n: weak.length }))}</button></div>
      ${showWeak ? `<div style="margin-top:12px">${list(weak)}</div>` : ''}` : ''}
    ${samples.length && !(rep.sources || []).length ? `<div class="row" style="justify-content:center;margin-top:10px"><button class="btn btn-quiet btn-sm" type="button" id="jSamples" aria-expanded="${samplesOpen}">
          ${icon(samplesOpen ? 'chevron-up' : 'chevron-down', 'icon-sm')}${esc(samplesOpen ? t('jobs.hideSamples', 'Hide example roles') : t('jobs.showSamples', 'Show {n} example roles', { n: samples.length }))}</button></div>
        ${samplesOpen ? `<div style="margin-top:12px">${head(t('jobs.gSamples', 'Example roles (not live openings)'), samples.length)}${list(samples)}</div>` : ''}` : ''}`;
  animateIn(box);
  const f = box.querySelector('#jFilter');
  f.addEventListener('input', () => { const pos = f.selectionStart; results(el); const n = el.querySelector('#jFilter'); n.focus(); n.setSelectionRange(pos, pos); });
  box.querySelectorAll('[data-place]').forEach((b) => b.addEventListener('click', () => { placeFilter = b.dataset.place; results(el); }));
  box.querySelector('#jSamples')?.addEventListener('click', () => { showSamples = !showSamples; results(el); });
  box.querySelector('#jWeak')?.addEventListener('click', () => { showWeak = !showWeak; results(el); });
}

function dropInner() {
  return resume.file
    ? `<span class="drop-icon">${icon('check')}</span><strong>${esc(resume.file)}</strong><span class="small quiet">${esc(t('jobs.loadedHint', 'Resume read. Choose another file to replace it.'))}</span>`
    : `<span class="drop-icon">${icon('upload')}</span><strong>${esc(t('jobs.dropT', 'Drop your resume here'))}</strong><span class="small quiet">${esc(t('jobs.drop', 'or tap to choose a PDF, Word or text file'))}</span>`;
}

async function readResume(file, el) {
  const fd = new FormData();
  fd.append('file', file);
  const drop = el.querySelector('#jDrop');
  drop.querySelector('.drop-icon').innerHTML = '<span class="spinner"></span>';
  try {
    const res = await api('/api/resume/parse', { method: 'POST', body: fd });
    resume = { text: res.text, file: file.name };
    setResume(resume);
    toast(t('jobs.loaded', 'Resume added'));
  } catch (err) {
    toast(err.message, 'bad');
  }
  drop.classList.toggle('loaded', !!resume.file);
  drop.querySelector('[data-drop-inner]').innerHTML = dropInner();
  const ta = el.querySelector('#jResume'); if (ta) ta.value = resume.text;
}

export function hoursField(value, id = 'jHours') {
  return `<div class="field">
    <label class="label" for="${id}">${esc(t('jobs.hours', 'Time you can give to learning'))}</label>
    <div class="slider hours">
      <div class="slider-top"><output class="slider-value num" for="${id}" data-hours-out>${esc(t('jobs.hoursV', '{n} hrs / week', { n: value }))}</output></div>
      <input class="range" type="range" id="${id}" name="hours" min="2" max="40" step="1" value="${value}" style="--pct:${((value - 2) / 38) * 100}%" />
    </div></div>`;
}

export function bindHours(root, onChange) {
  const range = root.querySelector('input[name=hours]');
  const out = root.querySelector('[data-hours-out]');
  range.addEventListener('input', () => {
    out.textContent = t('jobs.hoursV', '{n} hrs / week', { n: range.value });
    range.style.setProperty('--pct', `${((range.value - 2) / 38) * 100}%`);
    onChange?.(Number(range.value));
  });
}

export const jobs = {
  title: () => t('nav.jobs', 'Jobs'),
  sub: () => t('jobs.lede2', 'Matched to your profile and your resume. Pick a job to get a week-by-week plan to become ready for it.'),
  deps: [],
  render(el) {
    const last = state.jobs || {};
    resume = getResume();
    el.innerHTML = `
      <div class="jobs">
        <form class="card panel-pad stack jobs-form" id="jForm" style="margin-top:0" novalidate>
          <div class="field">
            <span class="label">${esc(t('jobs.resume', 'Resume'))}</span>
            <label class="drop ${resume.file ? 'loaded' : ''}" id="jDrop"><span data-drop-inner style="display:contents">${dropInner()}</span>
              <input type="file" class="sr-only" id="jFile" accept=".pdf,.docx,.txt" /></label>
            <button type="button" class="paste-toggle small" id="jPasteToggle" aria-expanded="${showPaste}">${esc(showPaste ? t('jobs.hidePaste', 'Hide resume text') : t('jobs.paste', 'Or paste the text instead'))}</button>
            <div ${showPaste ? '' : 'hidden'} id="jPasteBox"><label class="sr-only" for="jResume">${esc(t('jobs.paste', 'Or paste the text instead'))}</label>
              <textarea class="textarea" id="jResume" placeholder="${esc(t('jobs.pastePh', 'Paste the text of your resume'))}">${esc(resume.text)}</textarea></div>
            <p class="hint">${icon('lock', 'icon-sm')} ${esc(t('jobs.privacy', 'Kept only in this browser tab. Closing the tab removes it.'))}</p>
          </div>
          <div class="field"><label class="label" for="jRole">${esc(t('jobs.role', 'Role you want'))} <span class="quiet">(${esc(t('ob.optional', 'optional'))})</span></label>
            <div class="input-icon">${icon('target')}<input class="input" id="jRole" name="role" maxlength="120" value="${esc(last.role || '')}" placeholder="${esc(t('jobs.rolePh', 'e.g. Data analyst'))}" /></div>
            <p class="hint">${esc(t('jobs.roleHint', 'Leave it empty and we go by your resume.'))}</p>
            <div class="suggest">${ROLES.map((r) => `<button type="button" data-role="${esc(r)}">${esc(r)}</button>`).join('')}</div></div>
          ${tagInput('skills', last.skills || [], { label: t('jobs.skills', 'Skills not on your resume'), placeholder: t('jobs.skillsPh', 'Type a skill and press Enter'), suggestions: SKILL_IDEAS.filter((s) => !(last.skills || []).some((x) => x.toLowerCase() === s.toLowerCase())) })}
          ${hoursField(last.hours || 8)}
          ${state.profile ? `<p class="hint">${icon('user-round', 'icon-sm')} ${esc(t('jobs.usingProfile', 'Also using your profile: {e}{f}', { e: state.profile.education_level || '—', f: state.profile.field_of_study ? `, ${state.profile.field_of_study}` : '' }))}</p>` : ''}
          <button class="btn btn-primary btn-lg btn-block" type="submit" id="jGo" ${busy ? 'disabled' : ''}>${icon('sparkles')}${esc(t('jobs.find', 'Find my jobs'))}</button>
        </form>
        <div id="jResults" aria-live="polite"></div>
      </div>`;
    bindControls(el);
    bindHours(el);
    results(el);

    const form = el.querySelector('#jForm');
    el.querySelectorAll('[data-role]').forEach((b) => b.addEventListener('click', () => { el.querySelector('#jRole').value = b.dataset.role; }));
    const drop = el.querySelector('#jDrop');
    el.querySelector('#jFile').addEventListener('change', (e) => { const f = e.target.files[0]; if (f) readResume(f, el); });
    drop.addEventListener('dragover', (e) => { e.preventDefault(); drop.classList.add('drag'); });
    drop.addEventListener('dragleave', () => drop.classList.remove('drag'));
    drop.addEventListener('drop', (e) => { e.preventDefault(); drop.classList.remove('drag'); const f = e.dataTransfer.files[0]; if (f) readResume(f, el); });
    el.querySelector('#jPasteToggle').addEventListener('click', (e) => {
      showPaste = !showPaste;
      el.querySelector('#jPasteBox').hidden = !showPaste;
      e.target.setAttribute('aria-expanded', String(showPaste));
      e.target.textContent = showPaste ? t('jobs.hidePaste', 'Hide resume text') : t('jobs.paste', 'Or paste the text instead');
      if (showPaste) el.querySelector('#jResume').focus();
    });
    el.querySelector('#jResume').addEventListener('input', (e) => { resume.text = e.target.value; if (!resume.text) resume.file = ''; setResume(resume); });

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const fd = new FormData(form);
      const role = (fd.get('role') || '').trim();
      const skills = (fd.get('skills') || '').split(',').map((s) => s.trim()).filter(Boolean);
      const hours = Number(fd.get('hours')) || 8;
      if (!role && !resume.text.trim() && !skills.length) {
        toast(t('jobs.needSomething', 'Add your resume, a role or a few skills'), 'bad'); el.querySelector('#jFile').closest('label').focus(); return;
      }
      busy = true; showWeak = false; showSamples = false; placeFilter = 'all'; el.querySelector('#jGo').disabled = true; results(el);
      try {
        const report = await api('/api/opportunities/jobs/match', {
          method: 'POST',
          json: { profile: state.profile || {}, resume_text: resume.text, desired_role: role, skills },
        });
        saveJobs({ role, skills, hours, report, at: Date.now() });
      } catch (err) {
        toast(err.message, 'bad');
      } finally {
        busy = false;
        const go = el.querySelector('#jGo'); if (go) go.disabled = false;
        results(el);
        if (matchMedia('(max-width: 960px)').matches) el.querySelector('#jResults').scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  },
};
