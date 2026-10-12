/* Onboarding: one friendly question per screen, tap-to-choose controls. */
import { esc } from '../util.js';
import { t, getLang } from '../i18n.js';
import { icon } from '../icons.js';
import { toast } from '../ui.js';
import { state } from '../state.js';
import { STATES, CATEGORIES, EDUCATION, EXAMPLE, profilePayload } from '../profileFields.js';
import { chips, choiceCards, incomeSlider, typeahead, switchRow, bindControls } from '../components.js';
import { saveAndRun } from '../run.js';
import { api } from '../api.js';

export const EDU_ICONS = { '9th': 'school', '10th': 'school', '11th': 'book-open', '12th': 'book-open', Diploma: 'layers', Undergraduate: 'graduation-cap', Postgraduate: 'badge-check' };
export const FIELDS = ['Engineering', 'Science', 'Commerce', 'Arts', 'Medicine', 'Law', 'Agriculture', 'Computer Science'];
export const GOALS = [
  ['higher studies', 'goal.study', 'Higher studies', 'graduation-cap'],
  ['get a job', 'goal.job', 'Get a job', 'briefcase'],
  ['start a business', 'goal.business', 'Start a business', 'rocket'],
  ['learn a skill', 'goal.skill', 'Learn a new skill', 'zap'],
];

export const genderOptions = () => [['Female', t('g.female', 'Female')], ['Male', t('g.male', 'Male')], ['Other', t('g.other', 'Other')]];
export const eduLabel = ([v, en, hi]) => (getLang() === 'hi' ? hi : t(`edu.${v}`, en));
export const eduOptions = () => EDUCATION.map((e) => [e[0], eduLabel(e), EDU_ICONS[e[0]]]);

/** Canonical state name for typed input, or null. */
export const matchState = (v) => STATES.find((s) => s.toLowerCase() === String(v || '').trim().toLowerCase()) || null;

/** Split saved goals text back into chosen chips + free text. */
export function splitGoals(text) {
  const chosen = []; let rest = String(text || '');
  for (const [v] of GOALS) {
    const re = new RegExp(`(^|[,.;]\\s*)${v}(?=$|[,.;])`, 'i');
    if (re.test(rest)) { chosen.push(v); rest = rest.replace(re, '$1'); }
  }
  return { chosen, rest: rest.replace(/^[\s,.;]+|[\s,.;]+$/g, '') };
}
export const joinGoals = (chosen, rest) => [...chosen, rest].map((s) => (s || '').trim()).filter(Boolean).join(', ') || null;

let step = 1;
let dir = 'fwd';
let draft = null;
let described = null;   // what "Describe yourself" filled in, shown as chips

const FIELD_NAMES = {
  name: ['f.name', 'Name'], age: ['f.age', 'Age'], gender: ['f.gender', 'Gender'], state: ['f.state', 'State'],
  category: ['f.category', 'Category'], education_level: ['f.education', 'Education'], field_of_study: ['f.field', 'Field of study'],
  annual_income: ['f.income', 'Family income'], disability: ['f.disabilityShort', 'Disability'], goals: ['ob.s4', 'Goals'],
};

const QUESTIONS = [
  ['ob.q1', 'First, what should we call you?', 'ob.q1p', 'Only your name is required.'],
  ['ob.q2', 'What are you studying right now?', 'ob.q2p', 'Most scholarships depend on this.'],
  ['ob.q3', 'A little about your family', 'ob.q3p', 'Income, category and state decide which government schemes apply.'],
  ['ob.q4', 'What are you aiming for?', 'ob.q4p', 'Pick any that fit. Startup and skill schemes look at this.'],
];

function body() {
  const d = draft;
  if (step === 1) return `
    <div class="describe">
      <label class="label" for="f-describe">${icon('wand-sparkles', 'icon-sm')} ${esc(t('ob.describe', 'Describe yourself in one line'))} <span class="quiet">(${esc(t('ob.optional', 'optional'))})</span></label>
      <div class="describe-row">
        <textarea class="textarea" id="f-describe" rows="2" maxlength="600" placeholder="${esc(t('ob.describePh', "e.g. I'm Aisha, a 21-year-old girl from Bengaluru doing B.Tech, OBC, family income 3 lakh, I want a job"))}">${esc(described?.text || '')}</textarea>
        <button class="btn btn-secondary" type="button" id="obDescribe">${icon('sparkles', 'icon-sm')}${esc(t('ob.fillForMe', 'Fill in for me'))}</button>
      </div>
      ${described ? `<div class="describe-found" role="status">
        <p class="tiny quiet">${esc(t('ob.filled', 'Filled {n} answers. Check them on each step:', { n: described.found.length }))}</p>
        <div class="skills">${described.found.map((f) => `<span class="skill" title="${esc(t('ob.fromWords', 'from: "{w}"', { w: f.from }))}">${icon('check', 'icon-sm')}${esc(t(...(FIELD_NAMES[f.field] || [f.field, f.field])))}: ${esc(f.field === 'annual_income' ? '₹' + Number(f.value).toLocaleString('en-IN') : f.value === true ? t('yes', 'Yes') : f.value)}</span>`).join('')}</div>
      </div>` : ''}
    </div>
    <div class="field"><label class="label" for="f-name">${esc(t('f.name', 'Full name'))}</label>
      <input class="input input-lg" id="f-name" name="name" required maxlength="120" autocomplete="name" value="${esc(d.name || '')}" placeholder="${esc(t('ob.namePh', 'e.g. Aisha Kumar'))}" /></div>
    <div class="grid-2">
      <div class="field"><label class="label" for="f-age">${esc(t('f.age', 'Age'))}</label>
        <input class="input" id="f-age" name="age" type="number" inputmode="numeric" min="5" max="120" value="${esc(d.age ?? '')}" placeholder="21" /></div>
      ${chips('gender', genderOptions(), d.gender, { label: t('f.gender', 'Gender') })}
    </div>`;
  if (step === 2) return `
    ${choiceCards('education_level', eduOptions(), d.education_level)}
    <div class="field"><label class="label" for="f-field">${esc(t('f.field', 'Field of study'))}</label>
      <input class="input" id="f-field" name="field_of_study" maxlength="120" value="${esc(d.field_of_study || '')}" placeholder="${esc(t('ob.fieldPh', 'Type or pick one'))}" />
      <div class="suggest">${FIELDS.map((f) => `<button type="button" data-field="${esc(f)}">${esc(f)}</button>`).join('')}</div></div>`;
  if (step === 3) return `
    <div class="grid-2">
      ${typeahead('state', STATES, d.state, { label: t('f.state', 'State'), placeholder: t('ob.statePh', 'Start typing your state') })}
      ${chips('category', CATEGORIES.map((c) => [c, c]), d.category, { label: t('f.category', 'Category') })}
    </div>
    ${incomeSlider('annual_income', d.annual_income ?? 300000, { label: t('f.income', 'Family income per year (₹)'), hint: t('ob.incomeHint', 'Total for the whole family') })}
    ${switchRow('disability', t('f.disability', 'I have a disability of 40% or more'), d.disability)}
    <p class="notice notice-warn" id="obStateErr" hidden>${icon('info')}<span>${esc(t('ob.stateErr', 'Choose a state from the list, or leave it empty.'))}</span></p>`;
  const g = splitGoals(d.goals);
  return `
    ${chips('goal', GOALS.map(([v, k, en, ic]) => [v, t(k, en), ic]), g.chosen, { type: 'checkbox' })}
    <div class="field"><label class="label" for="f-goals">${esc(t('ob.moreGoals', 'Anything else? (optional)'))}</label>
      <textarea class="textarea" id="f-goals" name="goals_text" rows="3" maxlength="400" placeholder="${esc(t('f.goalsHint', 'For example: finish B.Tech, later start a company'))}">${esc(g.rest)}</textarea></div>`;
}

function read(form) {
  const fd = new FormData(form);
  const d = { ...draft };
  if (step === 1) {
    d.name = (fd.get('name') || '').trim() || null;
    d.age = fd.get('age') ? Number(fd.get('age')) : null;
    d.gender = fd.get('gender') || d.gender || null;
  } else if (step === 2) {
    d.education_level = fd.get('education_level') || d.education_level || null;
    d.field_of_study = (fd.get('field_of_study') || '').trim() || null;
  } else if (step === 3) {
    const raw = (fd.get('state') || '').trim();
    d.state = raw ? matchState(raw) : null;
    d._badState = !!raw && !d.state;
    d.category = fd.get('category') || d.category || null;
    d.annual_income = Number(fd.get('annual_income'));
    d.disability = fd.get('disability') === 'on';
  } else {
    d.goals = joinGoals(fd.getAll('goal'), fd.get('goals_text'));
  }
  return d;
}

export const onboarding = {
  full: true,
  title: () => t('ob.step', 'Step {n} of 4', { n: step }),
  render(el) {
    if (!draft) draft = { ...(state.profile || {}) };
    const [qk, qen, pk, pen] = QUESTIONS[step - 1];
    el.innerHTML = `
      <div class="wrap page"><section class="onboard">
        <div class="card onboard-card">
          <div class="ob-progress">
            <span class="small quiet num">${esc(t('ob.step', 'Step {n} of 4', { n: step }))}</span>
            <div class="ob-bar" role="progressbar" aria-valuemin="1" aria-valuemax="4" aria-valuenow="${step}"><span style="width:${step * 25}%"></span></div>
          </div>
          <form id="obForm" novalidate>
            <div class="ob-body ${dir === 'back' ? 'back' : ''} stack">
              <div><h1 class="ob-q">${esc(t(qk, qen))}</h1><p class="lede" style="margin-top:8px">${esc(t(pk, pen))}</p></div>
              ${body()}
              <p class="notice notice-warn" id="obError" hidden role="alert"></p>
            </div>
            <div class="ob-actions">
              ${step > 1 ? `<button class="btn btn-quiet" type="button" id="obBack">${icon('chevron-left')}${esc(t('ob.back', 'Back'))}</button>` : `<a class="btn btn-quiet" href="#/">${icon('chevron-left')}${esc(t('ob.cancel', 'Cancel'))}</a>`}
              <span class="spacer"></span>
              ${step > 1 && step < 4 ? `<button class="btn btn-quiet" type="button" id="obSkip">${esc(t('ob.skip', 'Skip for now'))}</button>` : ''}
              <button class="btn btn-primary btn-lg" type="submit" id="obNext">${step < 4 ? `${esc(t('ob.next', 'Next'))}${icon('arrow-right', 'arrow')}` : `${icon('sparkles')}${esc(t('ob.finish', 'Find my matches'))}`}</button>
            </div>
          </form>
        </div>
      </section></div>`;

    const form = el.querySelector('#obForm');
    bindControls(form);
    const first = form.querySelector('input:not([type=hidden]):not([type=radio]):not([type=checkbox]), textarea');
    (step === 1 ? form.querySelector('#f-name') : first)?.focus({ preventScroll: true });
    form.querySelectorAll('[data-field]').forEach((b) => b.addEventListener('click', () => { form.querySelector('#f-field').value = b.dataset.field; }));

    const go = (n, d) => { step = n; dir = d; onboarding.render(el); window.dispatchEvent(new Event('lp:title')); };
    el.querySelector('#obBack')?.addEventListener('click', () => { draft = read(form); go(step - 1, 'back'); });
    el.querySelector('#obSkip')?.addEventListener('click', () => go(step + 1, 'fwd'));
    el.querySelector('#obDescribe')?.addEventListener('click', async (e) => {
      const text = el.querySelector('#f-describe').value.trim();
      if (!text) { el.querySelector('#f-describe').focus(); return; }
      const btn = e.currentTarget;
      btn.disabled = true; btn.innerHTML = '<span class="spinner"></span>';
      try {
        const res = await api('/api/ml/describe', { method: 'POST', json: { text } });
        draft = { ...read(form), ...res.profile };
        described = { ...res, text };
        if (!res.found.length) toast(t('ob.nothingFound', 'Could not pick out any answers. Try adding your age, state or course.'), 'bad');
        onboarding.render(el);
      } catch (err) {
        toast(err.message, 'bad'); btn.disabled = false; btn.textContent = t('ob.fillForMe', 'Fill in for me');
      }
    });

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      draft = read(form);
      if (step === 1 && !draft.name) {
        const err = el.querySelector('#obError');
        err.textContent = t('ob.nameRequired', 'Enter your name to continue.'); err.hidden = false;
        form.querySelector('#f-name').focus();
        return;
      }
      if (step === 3 && draft._badState) { el.querySelector('#obStateErr').hidden = false; form.querySelector('#f-state').focus(); return; }
      if (step < 4) return go(step + 1, 'fwd');

      const btn = el.querySelector('#obNext');
      btn.disabled = true;
      btn.innerHTML = `<span class="spinner"></span>${esc(t('run.workingShort', 'Matching…'))}`;
      try {
        await saveAndRun(profilePayload(draft), () => { location.hash = '#/home'; });
        draft = null; step = 1; described = null;
      } catch (err) {
        btn.disabled = false; btn.textContent = t('ob.finish', 'Find my matches');
        toast(t('run.failed', 'Could not run the match: {msg}', { msg: err.message }), 'bad');
      }
    });
  },
};

/** "Try an example profile": jump to the last step with sample answers filled in. */
export function startWithExample() { draft = { ...EXAMPLE }; step = 4; dir = 'fwd'; }
