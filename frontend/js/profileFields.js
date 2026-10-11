/* Profile form fields, shared by the onboarding steps and the profile page. */
import { esc } from './util.js';
import { t } from './i18n.js';

export const STATES = [
  'Andhra Pradesh', 'Arunachal Pradesh', 'Assam', 'Bihar', 'Chhattisgarh', 'Goa', 'Gujarat', 'Haryana',
  'Himachal Pradesh', 'Jharkhand', 'Karnataka', 'Kerala', 'Madhya Pradesh', 'Maharashtra', 'Manipur',
  'Meghalaya', 'Mizoram', 'Nagaland', 'Odisha', 'Punjab', 'Rajasthan', 'Sikkim', 'Tamil Nadu', 'Telangana',
  'Tripura', 'Uttar Pradesh', 'Uttarakhand', 'West Bengal', 'Andaman and Nicobar Islands', 'Chandigarh',
  'Dadra and Nagar Haveli and Daman and Diu', 'Delhi', 'Jammu and Kashmir', 'Ladakh', 'Lakshadweep', 'Puducherry',
];
export const CATEGORIES = ['General', 'OBC', 'SC', 'ST', 'EWS'];
export const EDUCATION = [
  ['9th', '9th', '9वीं'], ['10th', '10th', '10वीं'], ['11th', '11th', '11वीं'], ['12th', '12th', '12वीं'],
  ['Diploma', 'Diploma', 'डिप्लोमा'], ['Undergraduate', 'Undergraduate (college degree)', 'स्नातक (कॉलेज डिग्री)'],
  ['Postgraduate', 'Postgraduate (master’s)', 'स्नातकोत्तर (मास्टर्स)'],
];
const GENDERS = [['Female', 'g.female', 'Female'], ['Male', 'g.male', 'Male'], ['Other', 'g.other', 'Other']];

export const EXAMPLE = {
  name: 'Aisha Kumar', age: 21, gender: 'Female', state: 'Karnataka', category: 'OBC',
  education_level: 'Undergraduate', field_of_study: 'Engineering', annual_income: 300000,
  disability: false, goals: 'Finish B.Tech and later start a company',
};

const opt = (value, label, current) =>
  `<option value="${esc(value)}" ${String(current ?? '') === String(value) ? 'selected' : ''}>${esc(label)}</option>`;

function select(name, labelKey, labelEn, options, current, hint = '') {
  return `<div class="field">
    <label class="label" for="f-${name}">${esc(t(labelKey, labelEn))}</label>
    <select class="select" id="f-${name}" name="${name}">
      ${opt('', t('f.choose', 'Choose'), current)}${options.join('')}
    </select>${hint ? `<p class="hint">${esc(hint)}</p>` : ''}
  </div>`;
}

function input(name, labelKey, labelEn, current, attrs = '', hint = '') {
  return `<div class="field">
    <label class="label" for="f-${name}">${esc(t(labelKey, labelEn))}</label>
    <input class="input" id="f-${name}" name="${name}" value="${esc(current ?? '')}" ${attrs} ${hint ? `aria-describedby="h-${name}"` : ''} />
    ${hint ? `<p class="hint" id="h-${name}">${esc(hint)}</p>` : ''}
  </div>`;
}

export const FIELD_HTML = {
  name: (p) => input('name', 'f.name', 'Full name', p.name, 'required autocomplete="name" maxlength="120"'),
  age: (p) => input('age', 'f.age', 'Age', p.age, 'type="number" inputmode="numeric" min="5" max="120"'),
  gender: (p) => select('gender', 'f.gender', 'Gender', GENDERS.map(([v, k, en]) => opt(v, t(k, en), p.gender)), p.gender),
  education_level: (p) => select('education_level', 'f.education', 'Education level',
    EDUCATION.map(([v, en, hi]) => opt(v, document.documentElement.lang === 'hi' ? hi : en, p.education_level)), p.education_level),
  field_of_study: (p) => input('field_of_study', 'f.field', 'Field of study', p.field_of_study, 'placeholder="Engineering, Commerce, Science…" maxlength="120"'),
  state: (p) => select('state', 'f.state', 'State', STATES.map((s) => opt(s, s, p.state)), p.state),
  category: (p) => select('category', 'f.category', 'Category', CATEGORIES.map((c) => opt(c, c, p.category)), p.category),
  annual_income: (p) => input('annual_income', 'f.income', 'Family income per year (₹)', p.annual_income,
    'type="number" inputmode="numeric" min="0" step="1000" placeholder="300000"',
    t('f.incomeHint', 'Total for the whole family. This is the amount on an income certificate.')),
  disability: (p) => `<label class="check"><input type="checkbox" name="disability" ${p.disability ? 'checked' : ''} /> ${esc(t('f.disability', 'I have a disability of 40% or more'))}</label>`,
  goals: (p) => `<div class="field">
    <label class="label" for="f-goals">${esc(t('f.goals', 'Goals'))}</label>
    <textarea class="textarea" id="f-goals" name="goals" rows="3" maxlength="500" aria-describedby="h-goals">${esc(p.goals ?? '')}</textarea>
    <p class="hint" id="h-goals">${esc(t('f.goalsHint', 'For example: finish B.Tech, later start a company'))}</p>
  </div>`,
};

/** Read every profile field present in `form` into a profile object. */
export function readFields(form, base = {}) {
  const fd = new FormData(form);
  const out = { ...base };
  const num = (v) => (v === null || v === '' ? null : Number(v));
  for (const key of ['name', 'gender', 'state', 'category', 'education_level', 'field_of_study', 'goals']) {
    if (fd.has(key)) out[key] = (fd.get(key) || '').trim() || null;
  }
  if (fd.has('age')) out.age = num(fd.get('age'));
  if (fd.has('annual_income')) out.annual_income = num(fd.get('annual_income'));
  if (form.querySelector('[name="disability"]')) out.disability = fd.get('disability') === 'on';
  return out;
}

export function profilePayload(p) {
  const keys = ['name', 'age', 'gender', 'state', 'category', 'education_level', 'field_of_study', 'annual_income', 'disability', 'goals'];
  return Object.fromEntries(keys.map((k) => [k, p[k] ?? (k === 'disability' ? false : null)]));
}
