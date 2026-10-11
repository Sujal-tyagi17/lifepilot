/* Profile and settings: edit everything on one page, language, theme, delete data. */
import { esc } from '../util.js';
import { t, getLang, setLang } from '../i18n.js';
import { icon, toast, confirmDialog } from '../ui.js';
import { state } from '../state.js';
import { FIELD_HTML, readFields, profilePayload } from '../profileFields.js';
import { saveAndRun } from '../run.js';
import { deleteEverything } from '../auth.js';
import { vaultClear } from '../vault.js';
import { store } from '../util.js';

export function applyTheme(choice) {
  store.setRaw('lp_theme', choice === 'system' ? null : choice);
  const dark = choice === 'dark' || (choice === 'system' && matchMedia('(prefers-color-scheme: dark)').matches);
  document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
}

export const profile = {
  title: () => t('nav.profile', 'Profile and settings'),
  deps: ['user'],
  render(el, _params, ctx) {
    const p = state.profile || {};
    const theme = store.raw('lp_theme') || 'system';
    el.innerHTML = `
      <form class="panel panel-pad stack" id="pForm" style="max-width:760px" novalidate>
        <h2 class="h2">${esc(t('prof.title', 'Your profile'))}</h2>
        ${FIELD_HTML.name(p)}
        <div class="grid-2">${FIELD_HTML.age(p)}${FIELD_HTML.gender(p)}</div>
        <div class="grid-2">${FIELD_HTML.education_level(p)}${FIELD_HTML.field_of_study(p)}</div>
        <div class="grid-2">${FIELD_HTML.state(p)}${FIELD_HTML.category(p)}</div>
        ${FIELD_HTML.annual_income(p)}
        ${FIELD_HTML.disability(p)}
        ${FIELD_HTML.goals(p)}
        <p class="notice notice-warn" id="pError" hidden role="alert"></p>
        <div class="row"><button class="btn btn-primary" type="submit" id="pSave">${esc(t('prof.save', 'Save and check again'))}</button></div>
      </form>

      <section class="panel panel-pad stack section" style="max-width:760px" aria-labelledby="hPrefs">
        <h2 class="h2" id="hPrefs">${esc(t('prof.prefs', 'Preferences'))}</h2>
        <div class="grid-2">
          <div class="field"><label class="label" for="pLang">${esc(t('prof.language', 'Language'))}</label>
            <select class="select" id="pLang"><option value="en" ${getLang() === 'en' ? 'selected' : ''}>English</option><option value="hi" ${getLang() === 'hi' ? 'selected' : ''}>हिन्दी</option></select></div>
          <div class="field"><label class="label" for="pTheme">${esc(t('prof.theme', 'Colours'))}</label>
            <select class="select" id="pTheme">${[['system', 'prof.system', 'Same as my device'], ['light', 'prof.light', 'Light'], ['dark', 'prof.dark', 'Dark']]
              .map(([v, k, en]) => `<option value="${v}" ${theme === v ? 'selected' : ''}>${esc(t(k, en))}</option>`).join('')}</select></div>
        </div>
      </section>

      <section class="panel panel-pad stack section" style="max-width:760px" aria-labelledby="hDel">
        <h2 class="h2" id="hDel">${esc(t('prof.delete', 'Delete my data'))}</h2>
        <p class="quiet">${esc(t('prof.deleteLede', 'Your profile, results and the files kept in this browser are deleted for good.'))}</p>
        <div class="row"><button class="btn btn-danger-quiet" type="button" id="pDelete">${icon('trash-2')}${esc(t('prof.delete', 'Delete my data'))}</button></div>
      </section>`;

    const form = el.querySelector('#pForm');
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const next = readFields(form, p);
      if (!next.name) {
        const err = el.querySelector('#pError');
        err.textContent = t('ob.nameRequired', 'Enter your name to continue.'); err.hidden = false;
        form.querySelector('[name="name"]').focus();
        return;
      }
      const btn = el.querySelector('#pSave');
      btn.disabled = true; btn.innerHTML = `<span class="spinner"></span>${esc(t('run.workingShort', 'Matching…'))}`;
      try {
        await saveAndRun(profilePayload(next));
        toast(t('prof.saved', 'Profile saved'));
        location.hash = '#/home';
      } catch (err) {
        toast(err.message, 'bad');
        btn.disabled = false; btn.textContent = t('prof.save', 'Save and check again');
      }
    });
    el.querySelector('#pLang').addEventListener('change', (e) => { setLang(e.target.value); ctx.refresh(); });
    el.querySelector('#pTheme').addEventListener('change', (e) => { applyTheme(e.target.value); ctx.refreshChrome(); });
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
        location.hash = '#/welcome';
      } catch (err) { toast(err.message, 'bad'); }
    });
  },
};
