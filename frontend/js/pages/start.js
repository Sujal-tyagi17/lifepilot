/* Welcome screen (first visit) and the 4-step onboarding. */
import { esc } from '../util.js';
import { t } from '../i18n.js';
import { icon, toast } from '../ui.js';
import { state } from '../state.js';
import { FIELD_HTML, readFields, profilePayload, EXAMPLE } from '../profileFields.js';
import { saveAndRun } from '../run.js';
import { signIn } from '../auth.js';

export const welcome = {
  title: () => '',
  render(el) {
    el.innerHTML = `
      <section class="welcome">
        <h1 class="display">${esc(t('welcome.title', 'Find the scholarships, schemes and jobs you qualify for.'))}</h1>
        <p class="lede" style="margin-top:18px">${esc(t('welcome.lede', 'Tell LifePilot a few things about yourself. It checks every scheme against your profile, shows why you qualify or what is missing, and what to do next.'))}</p>
        <div class="choices">
          <a class="btn btn-primary" href="#/start">${esc(t('welcome.start', 'Start without an account'))}</a>
          ${state.user ? '' : `<button class="btn btn-secondary" type="button" id="wSignIn">${icon('log-in')}${esc(t('welcome.signin', 'Sign in'))}</button>`}
          <button class="btn btn-quiet" type="button" id="wExample">${esc(t('welcome.example', 'Try an example profile'))}</button>
        </div>
        <p class="privacy">${icon('shield-check')}<span>${esc(t('welcome.privacy', 'Your profile is stored only on this LifePilot server. Your documents stay in this browser and are never uploaded.'))}</span></p>
      </section>`;
    el.querySelector('#wSignIn')?.addEventListener('click', signIn);
    el.querySelector('#wExample').addEventListener('click', () => {
      draft = { ...EXAMPLE };
      step = 4;
      location.hash = '#/start';
    });
  },
};

const STEPS = [
  { key: 'ob.s1', en: 'About you', lede: ['ob.s1.lede', 'Only your name is required. Everything else makes the matches sharper.'], fields: ['name', 'age', 'gender'] },
  { key: 'ob.s2', en: 'Studies', lede: ['ob.s2.lede', 'Most scholarships depend on your level of education and subject.'], fields: ['education_level', 'field_of_study'] },
  { key: 'ob.s3', en: 'Family and category', lede: ['ob.s3.lede', 'Income, category and state decide which government schemes apply to you.'], fields: ['state', 'category', 'annual_income', 'disability'] },
  { key: 'ob.s4', en: 'Goals', lede: ['ob.s4.lede', 'Startup and skills schemes look at your goals. Skip this if you like.'], fields: ['goals'] },
];

let step = 1;
let draft = null;

export const onboarding = {
  title: () => t('ob.step', 'Step {n} of 4', { n: step }),
  render(el) {
    if (!draft) draft = { ...(state.profile || {}) };
    const s = STEPS[step - 1];
    el.innerHTML = `
      <section class="onboard">
        <p class="quiet">${esc(t('ob.step', 'Step {n} of 4', { n: step }))}</p>
        <div class="progress" aria-hidden="true">${STEPS.map((_, i) =>
          `<span class="${i + 1 < step ? 'done' : i + 1 === step ? 'current' : ''}"></span>`).join('')}</div>
        <h1 class="display" style="font-size:clamp(1.7rem,3vw + .6rem,2.4rem)">${esc(t(s.key, s.en))}</h1>
        <p class="lede" style="margin-top:10px">${esc(t(...s.lede))}</p>
        <form class="stack" id="obForm" style="margin-top:28px" novalidate>
          ${s.fields.length > 2 && step === 3
            ? `<div class="grid-2">${FIELD_HTML.state(draft)}${FIELD_HTML.category(draft)}</div>${FIELD_HTML.annual_income(draft)}${FIELD_HTML.disability(draft)}`
            : step === 1
              ? `${FIELD_HTML.name(draft)}<div class="grid-2">${FIELD_HTML.age(draft)}${FIELD_HTML.gender(draft)}</div>`
              : s.fields.map((f) => FIELD_HTML[f](draft)).join('')}
          <p class="notice notice-warn" id="obError" hidden role="alert"></p>
          <div class="row row-wrap" style="margin-top:28px">
            ${step > 1 ? `<button class="btn btn-secondary" type="button" id="obBack">${icon('chevron-left')}${esc(t('ob.back', 'Back'))}</button>` : ''}
            <span class="spacer"></span>
            ${step > 1 && step < 4 ? `<button class="btn btn-quiet" type="button" id="obSkip">${esc(t('ob.skip', 'Skip for now'))}</button>` : ''}
            <button class="btn btn-primary" type="submit" id="obNext">${step < 4 ? `${esc(t('ob.next', 'Next'))}${icon('chevron-right')}` : esc(t('ob.finish', 'Find my matches'))}</button>
          </div>
        </form>
      </section>`;

    const form = el.querySelector('#obForm');
    form.querySelector('input, select, textarea')?.focus();

    el.querySelector('#obBack')?.addEventListener('click', () => {
      draft = readFields(form, draft); step -= 1; onboarding.render(el); window.dispatchEvent(new Event('lp:title'));
    });
    el.querySelector('#obSkip')?.addEventListener('click', () => {
      step += 1; onboarding.render(el); window.dispatchEvent(new Event('lp:title'));
    });
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      draft = readFields(form, draft);
      if (step === 1 && !draft.name) {
        const err = el.querySelector('#obError');
        err.textContent = t('ob.nameRequired', 'Enter your name to continue.');
        err.hidden = false;
        form.querySelector('[name="name"]').focus();
        return;
      }
      if (step < 4) { step += 1; onboarding.render(el); window.dispatchEvent(new Event('lp:title')); return; }

      const btn = el.querySelector('#obNext');
      btn.disabled = true;
      btn.innerHTML = `<span class="spinner"></span>${esc(t('run.workingShort', 'Matching…'))}`;
      try {
        await saveAndRun(profilePayload(draft), () => { location.hash = '#/home'; });
        draft = null; step = 1;
      } catch (err) {
        toast(t('run.failed', 'Could not run the match: {msg}', { msg: err.message }), 'bad');
      }
    });
  },
};

/** Called when the user picks "edit everything" from the profile page. */
export function restartOnboarding() { draft = { ...(state.profile || {}) }; step = 1; }
