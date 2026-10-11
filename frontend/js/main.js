/* LifePilot app entry: floating top navigation, hash router, startup. */
import { $, esc } from './util.js';
import { t, getLang, setLang } from './i18n.js';
import { icon } from './icons.js';
import { toast } from './ui.js';
import { api } from './api.js';
import { state, setState, subscribe } from './state.js';
import { initAuth, signIn, signOut } from './auth.js';
import { loadLatest, runAgents } from './run.js';
import { vaultList } from './vault.js';
import { initAssistant, openAssistant } from './assistant.js';
import { initPalette, openPalette, setCommands } from './palette.js';
import { downloadCalendar, printPlan } from './print.js';
import { landing } from './pages/landing.js';
import { onboarding } from './pages/start.js';
import { home } from './pages/home.js';
import { schemes, whatIf } from './pages/schemes.js';
import { jobs } from './pages/jobs.js';
import { documents } from './pages/documents.js';
import { how } from './pages/how.js';
import { profile, applyTheme } from './pages/profile.js';

const ROUTES = {
  '': landing, welcome: landing, start: onboarding, home, schemes, 'schemes/what-if': whatIf,
  jobs, documents, 'how-it-works': how, profile,
};

const NAV = [
  ['home', 'house', 'nav.home', 'Home'],
  ['schemes', 'landmark', 'nav.schemes', 'Schemes'],
  ['jobs', 'briefcase', 'nav.jobs', 'Jobs'],
  ['documents', 'folder-check', 'nav.documents', 'Documents'],
];

let current = { name: null, page: null, params: new URLSearchParams() };
let firstRoute = true;  // on first load keep focus at the top so "Skip to content" is the first Tab stop
let menuOpen = false;

function parseHash() {
  const raw = location.hash.replace(/^#\/?/, '');
  const [path, qs] = raw.split('?');
  return { name: path || '', params: new URLSearchParams(qs || '') };
}

/* ── Navigation chrome ── */
function movePill() {
  const nav = $('#navlinks');
  const pill = nav.querySelector('.nav-pill');
  const active = nav.querySelector('[aria-current="page"]');
  if (!pill) return;
  if (!active) { pill.style.opacity = '0'; return; }
  pill.style.opacity = '1';
  pill.style.width = `${active.offsetWidth}px`;
  pill.style.transform = `translateX(${active.offsetLeft - 4}px)`;
}

function renderChrome() {
  const section = current.name.split('/')[0];
  const link = ([key, ic, k, en], cls) =>
    `<a class="${cls}" href="#/${key}" ${section === key ? 'aria-current="page"' : ''}>${icon(ic)}<span>${esc(t(k, en))}</span></a>`;
  const asst = (cls) => `<button class="${cls}" type="button" data-assistant aria-controls="drawer" aria-expanded="false">${icon('message-circle')}<span>${esc(t('nav.assistant', 'Assistant'))}</span></button>`;

  $('#navlinks').innerHTML = `<span class="nav-pill" aria-hidden="true"></span>${NAV.map((n) => link(n, 'navlink')).join('')}${asst('navlink')}`;
  $('#tabbar').innerHTML = NAV.map((n) => link(n, 'tab')).join('') + asst('tab');
  requestAnimationFrame(movePill);

  const dark = document.documentElement.getAttribute('data-theme') === 'dark';
  const known = state.user || state.profileId;
  const who = state.user?.name || state.profile?.name || '';
  const initials = who.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join('') || '?';

  $('#navActions').innerHTML = `
    <button class="icon-btn lang-btn" type="button" id="langBtn" title="${esc(t('prof.language', 'Language'))}">${icon('languages', 'icon-sm')}<span lang="${getLang() === 'hi' ? 'en' : 'hi'}">${getLang() === 'hi' ? 'EN' : 'हिं'}</span></button>
    <button class="icon-btn" type="button" id="themeBtn" aria-label="${esc(dark ? t('theme.light', 'Switch to light mode') : t('theme.dark', 'Switch to dark mode'))}">${icon(dark ? 'sun' : 'moon')}</button>
    ${known ? `<div class="menu-wrap">
        <button class="icon-btn" type="button" id="menuBtn" aria-haspopup="menu" aria-expanded="${menuOpen}" aria-label="${esc(t('nav.account', 'Account menu'))}"><span class="avatar">${esc(initials)}</span></button>
        ${menuOpen ? `<div class="menu" role="menu" id="acctMenu">
          <div class="menu-head"><p style="font-weight:680">${esc(who || t('nav.guest', 'Guest'))}</p><p class="tiny quiet">${esc(state.user ? (state.user.email || '') : t('nav.guestNote', 'Saved in this browser'))}</p></div>
          <a role="menuitem" href="#/profile">${icon('user-round')}${esc(t('nav.profile', 'Profile and settings'))}</a>
          <a role="menuitem" href="#/how-it-works">${icon('route')}${esc(t('nav.how', 'How it works'))}</a>
          <button role="menuitem" type="button" data-cmd="palette">${icon('command')}${esc(t('palette.open', 'Commands'))} <span class="spacer"></span><kbd>Ctrl K</kbd></button>
          ${state.user
            ? `<button role="menuitem" type="button" data-cmd="signout">${icon('log-out')}${esc(t('auth.signout', 'Sign out'))}</button>`
            : `<button role="menuitem" type="button" data-cmd="signin">${icon('log-in')}${esc(t('auth.signinSave', 'Sign in to keep it everywhere'))}</button>`}
        </div>` : ''}
      </div>`
      : `<button class="btn btn-quiet btn-sm" type="button" data-cmd="signin">${esc(t('auth.signin', 'Sign in'))}</button>
         <a class="btn btn-primary btn-sm" href="#/start">${esc(t('land.start', 'Get started free'))}</a>`}`;

  $('#langBtn').addEventListener('click', toggleLang);
  $('#themeBtn').addEventListener('click', toggleTheme);
  $('#menuBtn')?.addEventListener('click', (e) => { e.stopPropagation(); menuOpen = !menuOpen; renderChrome(); if (menuOpen) $('#acctMenu a')?.focus(); });
  $('#navActions').querySelectorAll('[data-cmd]').forEach((b) => b.addEventListener('click', () => {
    menuOpen = false;
    ({ palette: openPalette, signin: signIn, signout: signOut })[b.dataset.cmd]();
    renderChrome();
  }));
  document.body.classList.toggle('tabbar-hidden', !state.profileId && (current.page === landing || current.page === onboarding));
}

function setTitle() {
  const title = current.page?.title?.() || '';
  document.title = title ? `${title} · LifePilot` : 'LifePilot · Scholarships, schemes and jobs you qualify for';
}

/* ── Router ── */
const ctx = {
  refresh() { renderChrome(); renderPage(true); },
  refreshChrome: () => renderChrome(),
};

function renderPage(animate = false) {
  const el = $('#content');
  const page = current.page;
  if (page.full) {
    page.render(el, current.params, ctx);
  } else {
    let body = el.querySelector(':scope > .wrap > #pageBody');
    if (!body || animate) {
      const sub = page.sub?.();
      el.innerHTML = `<div class="wrap page ${animate ? 'page-enter' : ''}">
        ${page.noHead ? '' : `<header class="page-head"><div><h1 class="h1">${esc(page.title())}</h1>${sub ? `<p class="lede">${esc(sub)}</p>` : ''}</div></header>`}
        <div id="pageBody"></div></div>`;
      body = el.querySelector('#pageBody');
    }
    page.render(body, current.params, ctx);
  }
  setTitle();
}

function route() {
  if (location.hash && !location.hash.startsWith('#/')) return; // in-page anchors
  let { name, params } = parseHash();
  if (name === 'welcome') name = '';
  if (name === 'home' && !state.profileId && !state.running) name = '';
  const page = ROUTES[name];
  if (!page) { location.replace('#/'); return; }
  const changed = current.name !== name;
  if (changed) current.page?.leave?.();
  current = { name, page, params };
  menuOpen = false;
  renderChrome();
  renderPage(changed);
  if (changed) {
    window.scrollTo({ top: 0, behavior: 'instant' in window ? 'instant' : 'auto' });
    if (!firstRoute) $('#content').focus({ preventScroll: true });
  }
  firstRoute = false;
}

subscribe((_s, keys) => {
  if (!current.page) return;
  if (keys.some((k) => ['user', 'profileId', 'profile'].includes(k))) renderChrome();
  if ((current.page.deps || []).some((d) => keys.includes(d))) renderPage(false);
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
  try { const h = await api('/api/health'); setState({ health: { ok: true, llm: h.llm_provider } }); }
  catch { setState({ health: { ok: false } }); }
}

async function boot() {
  initAssistant();
  initPalette();
  setCommands(commands());
  document.addEventListener('click', (e) => {
    if (e.target.closest('[data-assistant]')) openAssistant();
    if (menuOpen && !e.target.closest('.menu-wrap')) { menuOpen = false; renderChrome(); }
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && menuOpen) { menuOpen = false; renderChrome(); $('#menuBtn')?.focus(); }
  });
  window.addEventListener('hashchange', route);
  window.addEventListener('lp:title', setTitle);
  window.addEventListener('resize', movePill);
  window.addEventListener('scroll', () => $('#topnav').classList.toggle('scrolled', scrollY > 8), { passive: true });

  checkHealth();
  vaultList().then((vault) => setState({ vault }));
  await initAuth();
  route();
  if (state.profileId && !state.run) {
    try { await loadLatest(); } catch (err) { toast(err.message, 'bad'); }
  }
}

boot();
