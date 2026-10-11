/* Jobs: resume + target role in, ranked jobs with a visible fit breakdown out. */
import { esc } from '../util.js';
import { t } from '../i18n.js';
import { icon, toast } from '../ui.js';
import { api } from '../api.js';
import { state, saveJobs } from '../state.js';

const SEGMENTS = [
  ['skills', 'seg.skills', 'Skills'], ['role', 'seg.role', 'Role'],
  ['education', 'seg.education', 'Education'], ['field', 'seg.field', 'Field'],
];

let resumeText = '';  // kept in memory only; never written to storage
let typeFilter = 'all';
let busy = false;

function fitBar(j) {
  const parts = (j.fit_breakdown || []).filter((b) => b.points > 0);
  const label = parts.map((b) => `${t(`seg.${b.signal}`, b.signal)} ${Math.round(b.points)}`).join(', ');
  return `<div class="meter" role="img" aria-label="${esc(t('jobs.breakdown', 'How the score is made'))}: ${esc(label)}">
    ${parts.map((b) => `<span class="seg-${esc(b.signal)}" style="width:${b.points}%"></span>`).join('')}</div>`;
}

function jobItem(j) {
  const fit = Math.round((j.fit_score || 0) * 100);
  const url = j.url && /^https?:/.test(j.url) ? j.url : null;
  return `<li class="job">
    <div class="job-head">
      <div>
        <div class="row row-wrap" style="gap:8px;margin-bottom:6px">
          ${j.source === 'sample' ? `<span class="stamp stamp-sample" title="${esc(t('jobs.sampleNote', 'Example role, not a live opening. Check the company careers page.'))}">${esc(t('st.sample', 'Sample'))}</span>` : ''}
          ${j.eligible ? '' : `<span class="stamp stamp-partial">${esc(t('jobs.eduGap', 'Education gap'))}</span>`}
        </div>
        <h3 class="h3">${esc(j.title)}</h3>
        <p class="small quiet">${esc([j.company, j.location].filter(Boolean).join(' · '))}</p>
        <p class="small" style="margin-top:4px">${esc(t('jobs.salary', 'Salary'))}: ${esc(j.salary === 'Not disclosed' ? t('jobs.notDisclosed', 'Not disclosed') : j.salary)}</p>
      </div>
      <div class="fit"><p class="fit-value num">${fit}%</p><p class="fit-label">${esc(t('jobs.fit', 'fit'))}</p></div>
    </div>
    <div style="margin-top:12px">${fitBar(j)}</div>
    ${(j.skills_matched || []).length || (j.skills_missing || []).length ? `<div class="skills">
      ${(j.skills_matched || []).map((s) => `<span class="skill" title="${esc(t('jobs.have', 'You have'))}">${icon('check', 'icon-sm')} ${esc(s)}</span>`).join('')}
      ${(j.skills_missing || []).map((s) => `<span class="skill missing" title="${esc(t('jobs.learn', 'To learn'))}">${esc(s)}</span>`).join('')}
    </div>` : ''}
    ${(j.unmet || []).filter((u) => !u.startsWith('Skills to learn')).map((u) => `<p class="small gap" style="margin-top:8px">${esc(u)}</p>`).join('')}
    ${url ? `<div style="margin-top:14px"><a class="btn btn-secondary btn-sm" href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(t('jobs.applyAt', 'See it on the company site'))}${icon('external-link', 'icon-sm')}<span class="sr-only"> (opens a new tab)</span></a></div>` : ''}
  </li>`;
}

function results(el) {
  const box = el.querySelector('#jResults');
  const data = state.jobs;
  if (busy) { box.innerHTML = `<div class="panel panel-pad"><p class="working quiet"><span class="spinner"></span>${esc(t('jobs.finding', 'Finding jobs…'))}</p></div>`; return; }
  if (!data) { box.innerHTML = `<div class="panel empty"><p class="quiet">${esc(t('jobs.empty', 'Enter a role and find jobs.'))}</p></div>`; return; }
  const q = (el.querySelector('#jFilter')?.value || '').toLowerCase();
  const items = data.results.filter((j) => {
    if (typeFilter === 'remote' && j.job_type !== 'Remote') return false;
    if (typeFilter === 'onsite' && j.job_type === 'Remote') return false;
    return !q || `${j.title} ${j.company || ''} ${j.location || ''}`.toLowerCase().includes(q);
  });
  box.innerHTML = `
    <div class="toolbar">
      <label class="search"><span class="sr-only">Filter</span>${icon('search')}<input class="input" type="search" id="jFilter" value="${esc(q)}" placeholder="${esc(t('jobs.filterPh', 'Filter by title or company'))}" /></label>
      <div class="segmented" role="group" aria-label="${esc(t('jobs.filterType', 'Type'))}">
        ${[['all', 'jobs.anyType', 'Any'], ['remote', 'jobs.remote', 'Remote'], ['onsite', 'jobs.onsite', 'Office or hybrid']].map(([k, key, en]) =>
          `<button type="button" data-type="${k}" aria-pressed="${typeFilter === k}">${esc(t(key, en))}</button>`).join('')}
      </div>
    </div>
    <p class="small quiet" style="margin-bottom:8px">${esc(t('jobs.count', '{n} jobs', { n: items.length }))}</p>
    <div class="legend" aria-hidden="true">${SEGMENTS.map(([k, key, en]) => `<span><i class="seg-${k}"></i>${esc(t(key, en))}</span>`).join('')}</div>
    <section class="panel" style="margin-top:12px">
      ${items.length ? `<ul class="rows">${items.map(jobItem).join('')}</ul>`
        : `<p class="quiet" style="padding:20px">${esc(t('jobs.none', 'No jobs found for this role. Try another word.'))}</p>`}
    </section>`;
  const f = box.querySelector('#jFilter');
  f.addEventListener('input', () => { const pos = f.selectionStart; results(el); const n = el.querySelector('#jFilter'); n.focus(); n.setSelectionRange(pos, pos); });
  box.querySelectorAll('[data-type]').forEach((b) => b.addEventListener('click', () => { typeFilter = b.dataset.type; results(el); }));
}

async function readResume(file, el) {
  const fd = new FormData();
  fd.append('file', file);
  try {
    const res = await api('/api/resume/parse', { method: 'POST', body: fd });
    resumeText = res.text;
    el.querySelector('#jResume').value = resumeText;
    el.querySelector('#jDropLabel').textContent = file.name;
    toast(t('jobs.loaded', 'Resume added'));
  } catch (err) {
    toast(err.message, 'bad');
  }
}

export const jobs = {
  title: () => t('nav.jobs', 'Jobs'),
  deps: [],
  render(el) {
    const last = state.jobs || {};
    el.innerHTML = `
      <p class="lede" style="margin-bottom:24px">${esc(t('jobs.lede', 'Give your resume and the role you want. For each job you see a fit score, the skills you have and the skills to learn.'))}</p>
      <div class="jobs">
        <form class="panel panel-pad stack" id="jForm">
          <div class="field"><label class="label" for="jRole">${esc(t('jobs.role', 'Role you want'))}</label>
            <input class="input" id="jRole" name="role" required maxlength="120" value="${esc(last.role || '')}" placeholder="${esc(t('jobs.rolePh', 'e.g. Backend engineer, Accountant'))}" /></div>
          <div class="field"><label class="label" for="jSkills">${esc(t('jobs.skills', 'Your skills'))}</label>
            <input class="input" id="jSkills" name="skills" maxlength="300" value="${esc((last.skills || []).join(', '))}" placeholder="Python, SQL, Excel" aria-describedby="jSkillsHint" />
            <p class="hint" id="jSkillsHint">${esc(t('jobs.skillsHint', 'Separate with commas'))}</p></div>
          <div class="field">
            <span class="label">${esc(t('jobs.resume', 'Resume'))}</span>
            <label class="drop" id="jDrop">${icon('upload')}<span id="jDropLabel">${esc(t('jobs.drop', 'Choose a PDF, DOCX or TXT, or drop it here'))}</span>
              <input type="file" class="sr-only" id="jFile" accept=".pdf,.docx,.txt" /></label>
            <label class="sr-only" for="jResume">${esc(t('jobs.paste', 'Or paste the text of your resume'))}</label>
            <textarea class="textarea" id="jResume" placeholder="${esc(t('jobs.paste', 'Or paste the text of your resume'))}">${esc(resumeText)}</textarea>
          </div>
          <button class="btn btn-primary btn-block" type="submit" id="jGo" ${busy ? 'disabled' : ''}>${icon('search')}${esc(t('jobs.find', 'Find jobs'))}</button>
        </form>
        <div id="jResults" aria-live="polite"></div>
      </div>`;
    results(el);

    const drop = el.querySelector('#jDrop');
    el.querySelector('#jFile').addEventListener('change', (e) => { const f = e.target.files[0]; if (f) readResume(f, el); });
    drop.addEventListener('dragover', (e) => { e.preventDefault(); drop.classList.add('drag'); });
    drop.addEventListener('dragleave', () => drop.classList.remove('drag'));
    drop.addEventListener('drop', (e) => { e.preventDefault(); drop.classList.remove('drag'); const f = e.dataTransfer.files[0]; if (f) readResume(f, el); });
    el.querySelector('#jResume').addEventListener('input', (e) => { resumeText = e.target.value; });

    el.querySelector('#jForm').addEventListener('submit', async (e) => {
      e.preventDefault();
      const role = el.querySelector('#jRole').value.trim();
      const skills = el.querySelector('#jSkills').value.split(',').map((s) => s.trim()).filter(Boolean);
      busy = true; el.querySelector('#jGo').disabled = true; results(el);
      try {
        const res = await api('/api/opportunities/jobs/match', {
          method: 'POST',
          json: { profile: state.profile || {}, resume_text: resumeText, desired_role: role, skills },
        });
        saveJobs({ role, skills, results: res, at: Date.now() });
      } catch (err) {
        toast(err.message, 'bad');
      } finally {
        busy = false;
        const go = el.querySelector('#jGo'); if (go) go.disabled = false;
        results(el);
      }
    });
  },
};
