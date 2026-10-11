/* Jobs: resume + target role in, ranked jobs with a visible fit breakdown out. */
import { esc } from '../util.js';
import { t } from '../i18n.js';
import { icon, toast } from '../ui.js';
import { api } from '../api.js';
import { state, saveJobs } from '../state.js';
import { tagInput, bindControls, ring, animateIn } from '../components.js';

const SEGMENTS = [['skills', 'seg.skills', 'Skills'], ['role', 'seg.role', 'Role'], ['education', 'seg.education', 'Education'], ['field', 'seg.field', 'Field']];
const ROLES = ['Data analyst', 'Backend engineer', 'Frontend developer', 'Accountant', 'Sales executive', 'Teacher', 'Graphic designer'];
const SKILL_IDEAS = ['Python', 'SQL', 'Excel', 'Java', 'React', 'Communication', 'Tally'];

let resume = { text: '', file: '' };   // kept in memory only; never written to storage
let showPaste = false;
let typeFilter = 'all';
let busy = false;

/** Where the job came from, so search results never pass for real openings. */
function sourceStamp(j) {
  if (j.source === 'sample') return `<span class="stamp stamp-sample" title="${esc(t('jobs.sampleNote', 'Example role, not a live opening. Check the company careers page.'))}">${esc(t('st.sample', 'Sample'))}</span>`;
  if (j.source === 'web_search') return `<span class="stamp stamp-web" title="${esc(t('jobs.webNote', 'A web search result page, not a single job posting. Open it to find openings.'))}">${esc(t('st.web', 'Search result'))}</span>`;
  return `<span class="stamp stamp-live">${esc(t('st.live', 'Live listing'))}</span>`;
}

function fitColor(fit) { return fit >= 70 ? 'var(--green)' : fit >= 40 ? 'var(--saffron)' : 'var(--ink-3)'; }

function jobItem(j) {
  const fit = Math.round((j.fit_score || 0) * 100);
  const url = j.url && /^https?:/.test(j.url) ? j.url : null;
  const parts = (j.fit_breakdown || []).filter((b) => b.points > 0);
  return `<li class="job">
    <div class="job-head">
      <div style="min-width:0">
        <div class="row row-wrap" style="gap:8px;margin-bottom:8px">${sourceStamp(j)}
          ${j.eligible ? '' : `<span class="stamp stamp-partial">${esc(t('jobs.eduGap', 'Education gap'))}</span>`}</div>
        <h3 class="h3">${esc(j.title)}</h3>
        <p class="small quiet">${esc([j.company, j.location].filter(Boolean).join(' · '))}</p>
        <p class="small" style="margin-top:4px">${icon('wallet', 'icon-sm')} ${esc(j.salary === 'Not disclosed' ? t('jobs.notDisclosed', 'Salary not disclosed') : j.salary)}</p>
      </div>
      ${ring(fit, { size: 68, stroke: 7, color: fitColor(fit), label: `${fit}%`, cls: 'fit-ring' })}
    </div>
    ${parts.length ? `<div class="meter" style="margin-top:14px" role="img" aria-label="${esc(t('jobs.breakdown', 'How the score is made'))}: ${esc(parts.map((b) => `${t(`seg.${b.signal}`, b.signal)} ${Math.round(b.points)}`).join(', '))}">
      ${parts.map((b) => `<span class="seg-${esc(b.signal)}" style="width:0" data-width="${b.points}%"></span>`).join('')}</div>` : ''}
    ${(j.skills_matched || []).length || (j.skills_missing || []).length ? `<div class="skills">
      ${(j.skills_matched || []).map((s) => `<span class="skill" title="${esc(t('jobs.have', 'You have'))}">${icon('check', 'icon-sm')}${esc(s)}</span>`).join('')}
      ${(j.skills_missing || []).map((s) => `<span class="skill missing" title="${esc(t('jobs.learn', 'To learn'))}">${esc(s)}</span>`).join('')}
    </div>` : ''}
    ${(j.unmet || []).filter((u) => !u.startsWith('Skills to learn')).map((u) => `<p class="small gap" style="margin-top:8px">${esc(u)}</p>`).join('')}
    ${url ? `<div style="margin-top:14px"><a class="btn btn-secondary btn-sm" href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(j.source === 'web_search' ? t('jobs.openSearch', 'Open search results') : t('jobs.applyAt', 'See it on the company site'))}${icon('external-link', 'icon-sm')}<span class="sr-only"> (opens a new tab)</span></a></div>` : ''}
  </li>`;
}

function results(el) {
  const box = el.querySelector('#jResults');
  const data = state.jobs;
  if (busy) {
    box.innerHTML = `<div class="card panel-pad"><p class="working quiet"><span class="spinner"></span>${esc(t('jobs.finding', 'Finding jobs and checking your fit…'))}</p>
      ${[1, 2, 3].map(() => '<div class="skeleton sk-line" style="height:90px;margin:16px 0"></div>').join('')}</div>`;
    return;
  }
  if (!data) {
    box.innerHTML = `<div class="card empty"><span class="empty-icon">${icon('briefcase', 'icon-lg')}</span>
      <h2 class="h2">${esc(t('jobs.emptyT', 'Your matches will appear here'))}</h2>
      <p class="quiet">${esc(t('jobs.empty', 'Tell us the role you want and add your resume. We score every job and show the skills to learn.'))}</p></div>`;
    return;
  }
  const q = (el.querySelector('#jFilter')?.value || '').toLowerCase();
  const items = data.results.filter((j) => {
    if (typeFilter === 'remote' && j.job_type !== 'Remote') return false;
    if (typeFilter === 'onsite' && (j.job_type === 'Remote' || !j.job_type)) return false;
    return !q || `${j.title} ${j.company || ''} ${j.location || ''}`.toLowerCase().includes(q);
  });
  box.innerHTML = `
    <div class="toolbar">
      <label class="input-icon"><span class="sr-only">${esc(t('jobs.filterPh', 'Filter by title or company'))}</span>${icon('search')}<input class="input" type="search" id="jFilter" value="${esc(q)}" placeholder="${esc(t('jobs.filterPh', 'Filter by title or company'))}" /></label>
      <div class="segmented" role="group" aria-label="${esc(t('jobs.filterType', 'Type'))}">
        ${[['all', 'jobs.anyType', 'Any'], ['remote', 'jobs.remote', 'Remote'], ['onsite', 'jobs.onsite', 'Office or hybrid']].map(([k, key, en]) =>
          `<button type="button" data-type="${k}" aria-pressed="${typeFilter === k}">${esc(t(key, en))}</button>`).join('')}
      </div>
    </div>
    <div class="row row-wrap" style="justify-content:space-between;margin-bottom:12px">
      <p class="small quiet">${esc(t('jobs.count', '{n} jobs', { n: items.length }))}</p>
      <div class="legend" aria-hidden="true">${SEGMENTS.map(([k, key, en]) => `<span><i class="seg-${k}"></i>${esc(t(key, en))}</span>`).join('')}</div>
    </div>
    <section class="card">
      ${items.length ? `<ul class="rows">${items.map(jobItem).join('')}</ul>`
        : `<p class="quiet" style="padding:22px">${esc(t('jobs.none', 'No jobs found for this role. Try another word.'))}</p>`}
    </section>`;
  animateIn(box);
  const f = box.querySelector('#jFilter');
  f.addEventListener('input', () => { const pos = f.selectionStart; results(el); const n = el.querySelector('#jFilter'); n.focus(); n.setSelectionRange(pos, pos); });
  box.querySelectorAll('[data-type]').forEach((b) => b.addEventListener('click', () => { typeFilter = b.dataset.type; results(el); }));
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
    toast(t('jobs.loaded', 'Resume added'));
  } catch (err) {
    toast(err.message, 'bad');
  }
  drop.classList.toggle('loaded', !!resume.file);
  drop.querySelector('[data-drop-inner]').innerHTML = dropInner();
  const ta = el.querySelector('#jResume'); if (ta) ta.value = resume.text;
}

export const jobs = {
  title: () => t('nav.jobs', 'Jobs'),
  sub: () => t('jobs.lede', 'Tell us the role you want and add your resume. Each job gets a fit score, the skills you have and the skills to learn.'),
  deps: [],
  render(el) {
    const last = state.jobs || {};
    el.innerHTML = `
      <div class="jobs">
        <form class="card panel-pad stack jobs-form" id="jForm" style="margin-top:0">
          <div class="field"><label class="label" for="jRole">${esc(t('jobs.role', 'Role you want'))}</label>
            <div class="input-icon">${icon('target')}<input class="input" id="jRole" name="role" required maxlength="120" value="${esc(last.role || '')}" placeholder="${esc(t('jobs.rolePh', 'e.g. Data analyst'))}" /></div>
            <div class="suggest">${ROLES.map((r) => `<button type="button" data-role="${esc(r)}">${esc(r)}</button>`).join('')}</div></div>
          ${tagInput('skills', last.skills || [], { label: t('jobs.skills', 'Your skills'), placeholder: t('jobs.skillsPh', 'Type a skill and press Enter'), suggestions: SKILL_IDEAS.filter((s) => !(last.skills || []).some((x) => x.toLowerCase() === s.toLowerCase())) })}
          <div class="field">
            <span class="label">${esc(t('jobs.resume', 'Resume'))}</span>
            <label class="drop ${resume.file ? 'loaded' : ''}" id="jDrop"><span data-drop-inner style="display:contents">${dropInner()}</span>
              <input type="file" class="sr-only" id="jFile" accept=".pdf,.docx,.txt" /></label>
            <button type="button" class="paste-toggle small" id="jPasteToggle" aria-expanded="${showPaste}">${esc(showPaste ? t('jobs.hidePaste', 'Hide resume text') : t('jobs.paste', 'Or paste the text instead'))}</button>
            <div ${showPaste ? '' : 'hidden'} id="jPasteBox"><label class="sr-only" for="jResume">${esc(t('jobs.paste', 'Or paste the text instead'))}</label>
              <textarea class="textarea" id="jResume" placeholder="${esc(t('jobs.pastePh', 'Paste the text of your resume'))}">${esc(resume.text)}</textarea></div>
          </div>
          <button class="btn btn-primary btn-lg btn-block" type="submit" id="jGo" ${busy ? 'disabled' : ''}>${icon('sparkles')}${esc(t('jobs.find', 'Find my jobs'))}</button>
        </form>
        <div id="jResults" aria-live="polite"></div>
      </div>`;
    bindControls(el);
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
    el.querySelector('#jResume').addEventListener('input', (e) => { resume.text = e.target.value; });

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const role = el.querySelector('#jRole').value.trim();
      if (!role) { el.querySelector('#jRole').focus(); toast(t('jobs.needRole', 'Enter the role you want'), 'bad'); return; }
      const skills = (new FormData(form).get('skills') || '').split(',').map((s) => s.trim()).filter(Boolean);
      busy = true; el.querySelector('#jGo').disabled = true; results(el);
      try {
        const res = await api('/api/opportunities/jobs/match', {
          method: 'POST',
          json: { profile: state.profile || {}, resume_text: resume.text, desired_role: role, skills },
        });
        saveJobs({ role, skills, results: res, at: Date.now() });
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
