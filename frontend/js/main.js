/* LifePilot app entry: chrome (navigation, top bar), hash router, startup. */
import { $, esc } from './util.js';
import { t, getLang, setLang } from './i18n.js';
import { icon, toast } from './ui.js';
import { api } from './api.js';
import { state, setState, subscribe } from './state.js';
import { initAuth, signIn, signOut } from './auth.js';
import { loadLatest, runAgents } from './run.js';
import { vaultList } from './vault.js';
import { initAssistant, openAssistant } from './assistant.js';
import { initPalette, openPalette, setCommands } from './palette.js';
import { downloadCalendar, printPlan } from './print.js';
import { welcome, onboarding } from './pages/start.js';
import { home } from './pages/home.js';
import { schemes, whatIf } from './pages/schemes.js';
import { jobs } from './pages/jobs.js';
import { documents } from './pages/documents.js';
import { how } from './pages/how.js';
import { profile, applyTheme } from './pages/profile.js';

const ROUTES = {
  welcome, start: onboarding, home, schemes, 'schemes/what-if': whatIf, jobs, documents, 'how-it-works': how, profile,
};

const NAV = [
  ['home', 'house', 'nav.home', 'Home'],
  ['schemes', 'landmark', 'nav.schemes', 'Schemes'],
  ['jobs', 'briefcase', 'nav.jobs', 'Jobs'],
  ['documents', 'folder-check', 'nav.documents', 'Documents'],
];

let current = { name: null, page: null, params: new URLSearchParams() };
let firstRoute = true;  // on first load keep focus at the top so "Skip to content" is the first Tab stop

function parseHash() {
  const raw = location.hash.replace(/^#\/?/, '');
  const [path, qs] = raw.split('?');
  return { name: path || '', params: new URLSearchParams(qs || '') };
}

/* ── Chrome ── */
function renderChrome() {
  const section = current.name.split('/')[0];
  const navLink = ([key, ic, k, en], cls) =>
    `<a class="${cls}" href="#/${key}" ${section === key ? 'aria-current="page"' : ''}>${icon(ic)}<span>${esc(t(k, en))}</span></a>`;
  const asst = (cls) => `<button class="${cls}" type="button" data-assistant>${icon('message-circle')}<span>${esc(t('nav.assistant', 'Assistant'))}</span></button>`;

  $('#railNav').innerHTML = NAV.map((n) => navLink(n, 'nav-link')).join('') + asst('nav-link');
  $('#tabbar').innerHTML = NAV.map((n) => navLink(n, 'tab')).join('') + asst('tab');

  const footLink = (key, ic, k, en) => {
    const a = $(`.rail-foot [data-route="${key}"]`);
    a.innerHTML = `${icon(ic)}<span>${esc(t(k, en))}</span>`;
    if (section === key) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
  };
  footLink('how-it-works', 'route', 'nav.how', 'How it works');
  footLink('profile', 'user-round', 'nav.profile', 'Profile and settings');

  $('.brand-sub').textContent = t('brand.sub', 'Schemes and jobs, sorted');
  $('.skip-link').textContent = t('skip', 'Skip to content');

  $('#paletteBtn').innerHTML = `${icon('command', 'icon-sm')}<span class="sr-only">${esc(t('palette.open', 'Commands'))}</span><kbd aria-hidden="true">Ctrl K</kbd>`;
  $('#langBtn').innerHTML = `${icon('languages', 'icon-sm')}<span lang="${getLang() === 'hi' ? 'en' : 'hi'}">${getLang() === 'hi' ? 'English' : 'हिन्दी'}</span>`;
  const dark = document.documentElement.getAttribute('data-theme') === 'dark';
  $('#themeBtn').innerHTML = icon(dark ? 'sun' : 'moon');
  $('#themeBtn').setAttribute('aria-label', dark ? t('theme.light', 'Switch to light mode') : t('theme.dark', 'Switch to dark mode'));

  $('#authSlot').innerHTML = state.user
    ? `<span class="small" style="font-weight:600" title="${esc(state.user.email || '')}">${esc((state.user.name || '').split(' ')[0] || '')}</span>
       <button class="btn btn-quiet btn-icon" type="button" id="signOutBtn" aria-label="${esc(t('auth.signout', 'Sign out'))}">${icon('log-out')}</button>`
    : `<button class="btn btn-secondary btn-sm" type="button" id="signInBtn">${icon('log-in', 'icon-sm')}<span class="auth-label">${esc(t('auth.signin', 'Sign in'))}</span></button>`;
  $('#signInBtn')?.addEventListener('click', signIn);
  $('#signOutBtn')?.addEventListener('click', signOut);

  renderHealth();
}

function renderHealth() {
  const h = state.health;
  const el = $('#health');
  if (!h) { el.innerHTML = '<span class="dot"></span><span>…</span>'; return; }
  el.innerHTML = h.ok
    ? `<span class="dot dot-ok"></span><span>${esc(t('health.ok', 'Server online'))} · ${esc(h.llm === 'mock' ? t('health.engine', 'offline engine') : h.llm)}</span>`
    : `<span class="dot dot-bad"></span><span>${esc(t('health.offline', 'Server offline'))}</span>`;
}

function setTitle() {
  const title = current.page?.title?.() || 'LifePilot';
  $('#pageTitle').textContent = title;
  document.title = title === 'LifePilot' ? 'LifePilot' : `${title} · LifePilot`;
}

/* ── Router ── */
const ctx = {
  refresh() { renderChrome(); renderPage(); },
  refreshChrome: () => renderChrome(),
};

function renderPage() {
  const el = $('#content');
  current.page.render(el, current.params, ctx);
  setTitle();
}

function route() {
  let { name, params } = parseHash();
  if (!name) name = state.profileId ? 'home' : 'welcome';
  if (name === 'welcome' && state.profileId) name = 'home';
  if (name === 'home' && !state.profileId && !state.running) name = 'welcome';
  const page = ROUTES[name];
  if (!page) { location.replace('#/home'); return; }
  const changed = current.name !== name;
  current = { name, page, params };
  if (`#/${name}` !== location.hash.split('?')[0]) history.replaceState(null, '', `#/${name}${params.toString() ? `?${params}` : ''}`);
  renderChrome();
  renderPage();
  if (changed && !firstRoute) { window.scrollTo(0, 0); $('#content').focus({ preventScroll: true }); }
  firstRoute = false;
}

subscribe((_s, keys) => {
  if (!current.page) return;
  if (keys.includes('user')) renderChrome();
  if (keys.includes('health')) renderHealth();
  if ((current.page.deps || []).some((d) => keys.includes(d))) renderPage();
});

/* ── Commands ── */
function commands() {
  const go = (h) => () => { location.hash = h; };
  return [
    { icon: 'house', label: t('cmd.home', 'Open Home'), keys: 'dashboard', run: go('#/home') },
    { icon: 'landmark', label: t('cmd.schemes', 'Open Schemes'), keys: 'scholarship', run: go('#/schemes') },
    { icon: 'sliders-horizontal', label: t('cmd.whatif', 'Open What if'), keys: 'simulate income', run: go('#/schemes/what-if') },
    { icon: 'briefcase', label: t('cmd.jobs', 'Open Jobs'), keys: 'resume', run: go('#/jobs') },
    { icon: 'folder-check', label: t('cmd.docs', 'Open Documents'), keys: 'checklist vault', run: go('#/documents') },
    { icon: 'message-circle', label: t('cmd.asst', 'Ask the assistant'), keys: 'chat help', run: openAssistant },
    { icon: 'refresh-cw', label: t('cmd.rerun', 'Check again'), keys: 'run refresh', run: () => runAgents().catch((e) => toast(e.message, 'bad')) },
    { icon: 'calendar-plus', label: t('cmd.cal', 'Add deadlines to calendar'), keys: 'ics', run: downloadCalendar },
    { icon: 'printer', label: t('cmd.print', 'Print action plan'), keys: 'pdf', run: printPlan },
    { icon: 'user-round', label: t('cmd.profile', 'Edit profile'), keys: 'settings', run: go('#/profile') },
    { icon: 'route', label: t('cmd.how', 'How it works'), keys: 'agents trace', run: go('#/how-it-works') },
    { icon: 'moon', label: t('cmd.theme', 'Switch light/dark'), keys: 'theme dark', run: toggleTheme },
    { icon: 'languages', label: t('cmd.lang', 'Change language'), keys: 'hindi english', run: toggleLang },
  ];
}

function toggleTheme() {
  const dark = document.documentElement.getAttribute('data-theme') === 'dark';
  applyTheme(dark ? 'light' : 'dark');
  renderChrome();
}

function toggleLang() {
  setLang(getLang() === 'hi' ? 'en' : 'hi');
  setCommands(commands());
  ctx.refresh();
}

/* ── Startup ── */
async function checkHealth() {
  try {
    const h = await api('/api/health');
    setState({ health: { ok: true, llm: h.llm_provider } });
  } catch {
    setState({ health: { ok: false } });
  }
}

async function boot() {
  initAssistant();
  initPalette();
  setCommands(commands());
  document.addEventListener('click', (e) => { if (e.target.closest('[data-assistant]')) openAssistant(); });
  $('#paletteBtn').addEventListener('click', openPalette);
  $('#themeBtn').addEventListener('click', toggleTheme);
  $('#langBtn').addEventListener('click', toggleLang);
  window.addEventListener('hashchange', route);
  window.addEventListener('lp:title', setTitle);

  checkHealth();
  vaultList().then((vault) => setState({ vault }));
  await initAuth();
  route();
  if (state.profileId && !state.run) {
    try { await loadLatest(); } catch (err) { toast(err.message, 'bad'); }
  }
}

boot();
