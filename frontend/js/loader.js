/* The "checking your profile" loader: the six agents at work around the
   LifePilot plane. Each agent lights up in turn while the run is going. */
import { esc } from './util.js';
import { t } from './i18n.js';
import { logoMark } from './brand.js';

const AGENTS = [
  ['planner', 'Planner', 'Reading your profile'],
  ['research', 'Research', 'Gathering every scheme'],
  ['eligibility', 'Eligibility', 'Checking each rule'],
  ['document', 'Documents', 'Listing papers you need'],
  ['tracking', 'Tracking', 'Sorting by deadline'],
  ['roadmap', 'Roadmap', 'Building your next steps'],
];

/** Markup for the loader. Call startLoader(el) after inserting it. */
export function runLoader() {
  const sats = AGENTS.map((_, i) => `<span class="ld-sat" style="--a:${i * 60}deg"><i></i></span>`).join('');
  const sparks = Array.from({ length: 14 }, (_, i) =>
    `<span class="ld-spark" style="--a:${(i * 137.5) % 360}deg;--d:${(i % 7) * 0.31}s;--r:${70 + (i * 23) % 60}px"></span>`).join('');
  const steps = AGENTS.map(([k, name, what], i) => `<li class="ld-step" data-i="${i}">
      <span class="ld-dot" aria-hidden="true"><svg viewBox="0 0 16 16"><path d="M3.5 8.5 6.5 11.5 12.5 4.5"/></svg></span>
      <span class="ld-name">${esc(t(`ag.${k}`, name))}</span>
      <span class="ld-what">${esc(t(`ag.${k}Do`, what))}</span></li>`).join('');
  return `<section class="card ink ld" role="status" aria-live="polite">
    <div class="ld-stage" aria-hidden="true">
      <div class="ld-sweep"></div>
      <span class="ld-pulse"></span><span class="ld-pulse" style="animation-delay:-1s"></span><span class="ld-pulse" style="animation-delay:-2s"></span>
      <div class="ld-orbit ld-o1">${sats}</div>
      <div class="ld-orbit ld-o2"><span class="ld-moon"></span></div>
      <div class="ld-orbit ld-o3"><span class="ld-moon"></span><span class="ld-moon" style="--a:180deg"></span></div>
      ${sparks}
      <div class="ld-core">${logoMark('ld-logo')}</div>
    </div>
    <div class="ld-side">
      <p class="ld-kicker">${esc(t('ld.kicker', 'Six agents at work'))}</p>
      <h2 class="ld-title">${esc(t('run.working', 'Checking your profile against every scheme…'))}</h2>
      <ol class="ld-steps">${steps}</ol>
      <div class="ld-bar" aria-hidden="true"><span></span></div>
    </div>
  </section>`;
}

let startedAt = 0;   // when the current run began, so a re-render does not restart the animation

/** The run is over: the next loader starts from the first agent again. */
export function resetLoader() { startedAt = 0; }

/** Light the agents one after another until the loader leaves the page. */
export function startLoader(root) {
  const box = root.querySelector('.ld');
  if (!box) return;
  startedAt ||= Date.now();
  const steps = [...box.querySelectorAll('.ld-step')];
  const bar = box.querySelector('.ld-bar span');
  const tick = () => {
    if (!box.isConnected) { clearInterval(timer); return; }
    // The last agent keeps working until the run finishes
    const i = Math.min(steps.length - 1, Math.floor((Date.now() - startedAt) / 420));
    steps.forEach((s, j) => { s.classList.toggle('done', j < i); s.classList.toggle('now', j === i); });
    bar.style.width = `${Math.min(96, ((i + 0.6) / steps.length) * 100)}%`;
  };
  tick();
  const timer = setInterval(tick, 100);
}
