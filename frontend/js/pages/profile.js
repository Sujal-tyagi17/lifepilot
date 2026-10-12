/* Profile and settings: the same tap-to-choose controls as onboarding, plus preferences. */
import { esc, store } from '../util.js';
import { t, getLang, setLang, LANGS } from '../i18n.js';
import { icon, toast, confirmDialog } from '../ui.js';
import { state } from '../state.js';
import { STATES, CATEGORIES, profilePayload } from '../profileFields.js';
import { chips, choiceCards, incomeSlider, typeahead, switchRow, bindControls } from '../components.js';
import { saveAndRun } from '../run.js';
import { deleteEverything } from '../auth.js';
import { vaultClear } from '../vault.js';
import { genderOptions, eduOptions, matchState, GOALS, FIELDS, splitGoals, joinGoals } from './start.js';

export function applyTheme(choice) {
  store.setRaw('lp_theme', choice === 'system' ? null : choice);
  const dark = choice === 'dark' || (choice === 'system' && matchMedia('(prefers-color-scheme: dark)').matches);
  document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
}

const section = (id, title, inner) => `<section class="card panel-pad stack" aria-labelledby="${id}" style="margin-top:18px">
  <h2 class="h2" id="${id}">${esc(title)}</h2>${inner}</section>`;

export const profile = {
  title: () => t('nav.profile', 'Profile and settings'),
  sub: () => t('prof.sub', 'Change anything, then check again. Your matches update straight away.'),
  deps: ['user'],
  render(el, _params, ctx) {
    const p = state.profile || {};
    const g = splitGoals(p.goals);
    const theme = store.raw('lp_theme') || 'system';
    el.innerHTML = `
      <form id="pForm" novalidate style="max-width:820px">
        ${section('pAbout', t('ob.s1', 'About you'), `
          <div class="field"><label class="label" for="f-name">${esc(t('f.name', 'Full name'))}</label>
            <input class="input" id="f-name" name="name" required maxlength="120" autocomplete="name" value="${esc(p.name || '')}" /></div>
          <div class="grid-2">
            <div class="field"><label class="label" for="f-age">${esc(t('f.age', 'Age'))}</label>
              <input class="input" id="f-age" name="age" type="number" inputmode="numeric" min="5" max="120" value="${esc(p.age ?? '')}" /></div>
            ${chips('gender', genderOptions(), p.gender, { label: t('f.gender', 'Gender') })}
          </div>`)}
        ${section('pStudy', t('ob.s2', 'Studies'), `
          ${choiceCards('education_level', eduOptions(), p.education_level)}
          <div class="field"><label class="label" for="f-field">${esc(t('f.field', 'Field of study'))}</label>
            <input class="input" id="f-field" name="field_of_study" maxlength="120" value="${esc(p.field_of_study || '')}" />
            <div class="suggest">${FIELDS.map((f) => `<button type="button" data-field="${esc(f)}">${esc(f)}</button>`).join('')}</div></div>`)}
        ${section('pFamily', t('ob.s3', 'Family and category'), `
          <div class="grid-2">
            ${typeahead('state', STATES, p.state, { label: t('f.state', 'State'), placeholder: t('ob.statePh', 'Start typing your state') })}
            ${chips('category', CATEGORIES.map((c) => [c, c]), p.category, { label: t('f.category', 'Category') })}
          </div>
          ${incomeSlider('annual_income', p.annual_income ?? 300000, { label: t('f.income', 'Family income per year (₹)'), hint: t('ob.incomeHint', 'Total for the whole family') })}
          ${switchRow('disability', t('f.disability', 'I have a disability of 40% or more'), p.disability)}`)}
        ${section('pGoals', t('ob.s4', 'Goals'), `
          ${chips('goal', GOALS.map(([v, k, en, ic]) => [v, t(k, en), ic]), g.chosen, { type: 'checkbox' })}
          <div class="field"><label class="label" for="f-goals">${esc(t('ob.moreGoals', 'Anything else? (optional)'))}</label>
            <textarea class="textarea" id="f-goals" name="goals_text" rows="3" maxlength="400">${esc(g.rest)}</textarea></div>`)}
        <p class="notice notice-warn" id="pError" hidden role="alert" style="margin-top:18px"></p>
        <div class="row save-bar">
          <button class="btn btn-primary btn-lg" type="submit" id="pSave">${icon('sparkles')}${esc(t('prof.save', 'Save and check again'))}</button></div>
      </form>

      <div style="max-width:820px">
        ${section('hPrefs', t('prof.prefs', 'Preferences'), `
          <div class="grid-2">
            ${chips('lang', LANGS.map((l) => [l.code, l.native]), getLang(), { label: t('prof.language', 'Language'), id: 'pLang' })}
            ${chips('theme', [['system', t('prof.system', 'Same as my device')], ['light', t('prof.light', 'Light')], ['dark', t('prof.dark', 'Dark')]], theme, { label: t('prof.theme', 'Colours'), id: 'pTheme' })}
          </div>`)}
        ${section('hDel', t('prof.delete', 'Delete my data'), `
          <p class="quiet">${esc(t('prof.deleteLede', 'Your profile, results and the files kept in this browser are deleted for good.'))}</p>
          <div class="row"><button class="btn btn-danger-quiet" type="button" id="pDelete">${icon('trash-2')}${esc(t('prof.delete', 'Delete my data'))}</button></div>`)}
      </div>`;

    const form = el.querySelector('#pForm');
    bindControls(el);
    form.querySelectorAll('[data-field]').forEach((b) => b.addEventListener('click', () => { form.querySelector('#f-field').value = b.dataset.field; }));

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const fd = new FormData(form);
      const err = el.querySelector('#pError');
      const rawState = (fd.get('state') || '').trim();
      const next = {
        ...p,
        name: (fd.get('name') || '').trim() || null,
        age: fd.get('age') ? Number(fd.get('age')) : null,
        gender: fd.get('gender') || null,
        education_level: fd.get('education_level') || null,
        field_of_study: (fd.get('field_of_study') || '').trim() || null,
        state: rawState ? matchState(rawState) : null,
        category: fd.get('category') || null,
        annual_income: Number(fd.get('annual_income')),
        disability: fd.get('disability') === 'on',
        goals: joinGoals(fd.getAll('goal'), fd.get('goals_text')),
      };
      if (!next.name) { err.textContent = t('ob.nameRequired', 'Enter your name to continue.'); err.hidden = false; form.querySelector('#f-name').focus(); return; }
      if (rawState && !next.state) { err.textContent = t('ob.stateErr', 'Choose a state from the list, or leave it empty.'); err.hidden = false; form.querySelector('#f-state').focus(); return; }
      const btn = el.querySelector('#pSave');
      btn.disabled = true; btn.innerHTML = `<span class="spinner"></span>${esc(t('run.workingShort', 'Matching…'))}`;
      try {
        // Go to Home as soon as the profile is saved, so the loader shows while the agents run
        await saveAndRun(profilePayload(next), () => { location.hash = '#/home'; });
        toast(t('prof.saved', 'Profile saved'));
      } catch (ex) {
        toast(ex.message, 'bad');
        if (btn.isConnected) { btn.disabled = false; btn.textContent = t('prof.save', 'Save and check again'); }
      }
    });
    el.querySelectorAll('#pLang input').forEach((r) => r.addEventListener('change', async () => { await setLang(r.value); ctx.refresh(); }));
    el.querySelectorAll('#pTheme input').forEach((r) => r.addEventListener('change', () => { applyTheme(r.value); ctx.refreshChrome(); }));
    el.querySelector('#pDelete').addEventListener('click', async () => {
      const ok = await confirmDialog({
        title: t('prof.delete', 'Delete my data'),
        body: t('prof.deleteLede', 'Your profile, results and the files kept in this browser are deleted for good.'),
        confirm: t('prof.deleteConfirm', 'Yes, delete everything'), danger: true,
      });
      if (!ok) return;
      try {
        await deleteEverything(vaultClear);
        toast(t('prof.deleted', 'Your data was deleted'));
        location.hash = '#/';
      } catch (ex) { toast(ex.message, 'bad'); }
    });
  },
};
