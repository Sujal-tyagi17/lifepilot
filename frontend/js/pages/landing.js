/* Landing page: what LifePilot does, a live demo on real rules, and how to start. */
import { esc, fmtINR, daysLeft, matchStatus } from '../util.js';
import { t } from '../i18n.js';
import { icon } from '../icons.js';
import { state } from '../state.js';
import { api } from '../api.js';
import { signIn } from '../auth.js';
import { startWithExample } from './start.js';
import { countUp, reveal } from '../components.js';
import { stamp } from '../ui.js';
import { rosette, miniRosette, logoMark } from '../brand.js';
import { burst, splitWords } from '../fx.js';

// Fictional sample students. Their results are computed live by the rule engine.
const SAMPLES = [
  { initials: 'AK', name: 'Aisha, 21', facts: ['B.Tech', 'OBC', 'Karnataka', '₹3 lakh/yr'],
    profile: { name: 'Aisha', age: 21, gender: 'Female', state: 'Karnataka', category: 'OBC', education_level: 'Undergraduate', field_of_study: 'Engineering', annual_income: 300000, goals: 'start a company' } },
  { initials: 'RK', name: 'Rohan, 17', facts: ['Class 12', 'SC', 'Bihar', '₹1.8 lakh/yr'],
    profile: { name: 'Rohan', age: 17, gender: 'Male', state: 'Bihar', category: 'SC', education_level: '12th', field_of_study: 'Science', annual_income: 180000 } },
  { initials: 'MP', name: 'Meera, 23', facts: ['M.Sc Physics', 'General', 'Maharashtra', '₹4 lakh/yr'],
    profile: { name: 'Meera', age: 23, gender: 'Female', state: 'Maharashtra', category: 'General', education_level: 'Postgraduate', field_of_study: 'Physics', annual_income: 400000 } },
];

/* Small moving pictures for the four headline features. */
const ART = {
  scan: `<div class="art-doc"><i></i><i></i><i></i><i class="short"></i><span class="art-scanline"></span><b class="art-tick">✓</b></div>`,
  plan: `<div class="art-weeks">${[78, 54, 92, 36].map((w, i) => `<div><em>W${i + 1}</em><span style="--w:${w}%;--d:${i * 0.18}s"></span></div>`).join('')}</div>`,
  map: `<svg class="art-map" viewBox="0 0 220 120"><g class="edges">${[[40, 60, 110, 28], [40, 60, 110, 92], [110, 28, 180, 60], [110, 92, 180, 60], [110, 28, 110, 92], [40, 60, 180, 60]].map(([a, b, c, d]) => `<line x1="${a}" y1="${b}" x2="${c}" y2="${d}" />`).join('')}</g>
    <circle class="n doc" cx="40" cy="60" r="11" /><rect class="n sch" x="99" y="17" width="22" height="22" rx="6" /><rect class="n sch" x="99" y="81" width="22" height="22" rx="6" /><rect class="n sch b" x="169" y="49" width="22" height="22" rx="6" /></svg>`,
  voice: `<div class="art-eq">${Array.from({ length: 14 }, (_, i) => `<span style="--d:${(i * 0.07).toFixed(2)}s"></span>`).join('')}</div>`,
};

const WORDS = () => [t('land.w1', 'scholarships'), t('land.w2', 'schemes'), t('land.w3', 'jobs')];

let timers = [];
let first = true;   // the first stamp waits for the opening sequence
const clearTimers = () => { timers.forEach(clearInterval); timers = []; };

async function showSample(el, i) {
  const s = SAMPLES[i];
  const card = el.querySelector('#demoCard');
  el.querySelectorAll('.demo-dots button').forEach((b, j) => b.setAttribute('aria-pressed', String(i === j)));
  card.querySelector('.avatar').textContent = s.initials;
  card.querySelector('.demo-person').textContent = s.name;
  card.querySelector('.demo-facts').innerHTML = s.facts.map((f) => `<span>${esc(f)}</span>`).join('');
  const list = card.querySelector('.demo-list');
  try {
    const res = s.result || (s.result = await api('/api/agent/simulate', { method: 'POST', json: { ...s.profile, owned_documents: [] } }));
    const ins = res.insights;
    const elig = res.matches.filter((m) => matchStatus(m) === 'eligible');
    const shown = (elig.length ? elig : res.matches.filter((m) => matchStatus(m) === 'partial')).slice(0, 3);
    const n = card.querySelector('#demoN');
    card.querySelector('#demoStamp').innerHTML = elig.length ? stamp('eligible', 'stamp-press') : stamp('partial', 'stamp-press');
    if (elig.length) setTimeout(() => burst(card.querySelector('#demoStamp .stamp'), { count: 18, spread: 80 }), first ? 1500 : 420);
    first = false;
    countUp(n, ins.eligible_count);
    countUp(card.querySelector('#demoAmt'), ins.estimated_annual_benefit, (v) => fmtINR(v));
    list.innerHTML = shown.map((m) => `<li><span>${esc(m.title)}</span>${stamp(matchStatus(m))}</li>`).join('');
    const next = elig.map((m) => daysLeft(m.deadline)).filter((d) => d !== null && d >= 0).sort((a, b) => a - b)[0];
    el.querySelector('#floatDeadline').textContent = next !== undefined
      ? t('land.floatDeadline', 'Next deadline in {d} days', { d: next })
      : t('land.floatRules', 'Every rule checked');
  } catch {
    list.innerHTML = `<li class="quiet">${esc(t('err.network', 'Could not reach the server. Check that LifePilot is running.'))}</li>`;
  }
}

/** The paper plane flies once along the dotted route across the hero, then rests. */
function flyPlane(el) {
  const plane = el.querySelector('.flight-plane');
  const path = el.querySelector('#flightPath');
  const svg = el.querySelector('.flight');
  const hero = el.querySelector('.hero-ink');
  if (!plane || !path || matchMedia('(prefers-reduced-motion: reduce)').matches) { plane?.remove(); return; }
  const go = () => {
    const box = svg.getBoundingClientRect(), hb = hero.getBoundingClientRect();
    const sx = box.width / 1200, sy = box.height / 600, len = path.getTotalLength();
    const frames = [];
    for (let i = 0; i <= 48; i++) {
      const p = path.getPointAtLength((len * i) / 48), q = path.getPointAtLength(Math.min(len, (len * i) / 48 + 4));
      const x = box.left - hb.left + p.x * sx, y = box.top - hb.top + p.y * sy;
      const ang = Math.atan2((q.y - p.y) * sy, (q.x - p.x) * sx) * 180 / Math.PI + 22;
      frames.push({ transform: `translate(${x}px, ${y}px) translate(-50%, -50%) rotate(${ang}deg) scale(${0.7 + 0.5 * Math.sin(Math.PI * i / 48)})`, opacity: i < 2 || i > 46 ? 0 : 1 });
    }
    plane.animate(frames, { duration: 3200, delay: 900, easing: 'cubic-bezier(.45,.05,.3,1)', fill: 'both' });
  };
  requestAnimationFrame(go);
}

export const landing = {
  title: () => '',
  full: true,
  render(el) {
    clearTimers();
    const has = !!state.profileId;
    const startBtn = has
      ? `<a class="btn btn-primary btn-lg magnetic" href="#/home">${esc(t('land.open', 'Open my dashboard'))}${icon('arrow-right', 'arrow')}</a>`
      : `<a class="btn btn-primary btn-lg magnetic" href="#/start">${esc(t('land.start', 'Get started free'))}${icon('arrow-right', 'arrow')}</a>`;
    const words = WORDS();
    el.innerHTML = `
    <section class="hero-ink ink" data-parallax aria-labelledby="heroTitle">
      <div class="hero-rosette">${rosette({ cls: 'ros-draw' })}</div>
      <svg class="flight" viewBox="0 0 1200 600" preserveAspectRatio="none" aria-hidden="true">
        <path id="flightPath" d="M-40 560 C 240 520, 380 300, 640 330 S 980 180, 1240 60" fill="none" stroke="rgba(255,193,77,.45)" stroke-width="2" stroke-dasharray="2 12" stroke-linecap="round" vector-effect="non-scaling-stroke" />
      </svg>
      <span class="flight-plane" aria-hidden="true">${logoMark('plane-only')}</span>
      <div class="wrap hero">
        <div class="hero-copy">
          <span class="badge badge-ink"><span class="dot">${icon('check', 'icon-sm')}</span>${esc(t('land.badge', 'Free · Hindi and English · Works offline'))}</span>
          <h1 class="hero-title" id="heroTitle">${esc(t('land.h1a', 'Find the'))}<br />
            <span class="cycle" aria-hidden="true">${words.map((w, i) => `<span class="${i === 0 ? 'on' : ''}">${esc(w)}</span>`).join('')}</span><br />
            ${esc(t('land.h1b', 'you qualify for.'))}
            <span class="sr-only">${esc(words.join(', '))}</span></h1>
          <p class="hero-lede">${esc(t('land.lede', 'LifePilot checks every rule of every scheme against your profile, matches jobs to your resume, and turns it into a plan: what to apply for, which documents to get, and what to learn next.'))}</p>
          <div class="hero-ctas">
            ${startBtn}
            ${state.user ? '' : `<button class="btn btn-ghost-ink btn-lg" type="button" data-signin>${icon('log-in')}${esc(t('auth.signin', 'Sign in'))}</button>`}
            ${has ? '' : `<button class="btn btn-quiet-ink btn-lg" type="button" id="tryExample">${icon('play')}${esc(t('land.example', 'Try a sample profile'))}</button>`}
          </div>
          <p class="hero-note">
            <span>${icon('check', 'icon-sm')}${esc(t('land.n1', 'No account needed'))}</span>
            <span>${icon('check', 'icon-sm')}${esc(t('land.n2', 'About 2 minutes'))}</span>
            <span>${icon('check', 'icon-sm')}${esc(t('land.n3', 'Documents never leave your device'))}</span>
          </p>
        </div>

        <div class="demo" aria-label="${esc(t('land.demo', 'Live preview'))}">
          <div class="float float-1">${icon('scale')}<span>${esc(t('land.float1', 'Rules decide, not guesses'))}</span></div>
          <div class="float float-2">${icon('calendar-clock')}<span id="floatDeadline">${esc(t('land.floatRules', 'Every rule checked'))}</span></div>
          <div class="float float-3">${icon('languages')}<span>हिन्दी · English</span></div>
          <div class="demo-card certificate" id="demoCard" data-tilt>
            <div class="cert-corner">${miniRosette()}</div>
            <div class="demo-top"><span class="avatar">AK</span><div><p class="demo-person">Aisha, 21</p>
              <p class="tiny quiet">${esc(t('land.demoNote', 'Live preview · real results from the rule engine'))}</p></div></div>
            <div class="demo-facts"></div>
            <div class="demo-verdict">
              <div><p class="small quiet">${esc(t('land.qualifies', 'Qualifies for'))}</p>
                <p class="demo-big"><span id="demoN" class="num">0</span> ${esc(t('land.schemes', 'schemes'))}</p>
                <p class="small"><span id="demoAmt" class="num" style="font-weight:700">₹0</span> ${esc(t('land.perYear', 'a year'))}</p></div>
              <div id="demoStamp"></div>
            </div>
            <ul class="demo-list"></ul>
            <div class="demo-foot"><span>${esc(t('land.sample', 'Sample students'))}</span>
              <div class="demo-dots">${SAMPLES.map((s, i) => `<button type="button" aria-label="${esc(s.name)}" aria-pressed="${i === 0}" data-sample="${i}"></button>`).join('')}</div></div>
          </div>
        </div>
      </div>
      <div class="microline" aria-hidden="true"></div>
    </section>

    <div class="wrap">
      <section class="band" id="how" aria-labelledby="howTitle">
        <div class="band-head reveal"><h2 class="h1" id="howTitle">${esc(t('land.howT', 'From “am I eligible?” to a plan in three steps'))}</h2></div>
        <ol class="steps3 flightline">
          <li class="card step-card reveal"><h3 class="h2">${esc(t('land.s1', 'Tell us about you'))}</h3><p>${esc(t('land.s1p', 'One question at a time: studies, family income, category, state. Skip anything you are unsure of.'))}</p></li>
          <li class="card step-card reveal"><h3 class="h2">${esc(t('land.s2', 'We check every rule'))}</h3><p>${esc(t('land.s2p', 'Each scheme’s rules are checked one by one. You see exactly why you qualify, or what is missing.'))}</p></li>
          <li class="card step-card reveal"><h3 class="h2">${esc(t('land.s3', 'Get your plan'))}</h3><p>${esc(t('land.s3p', 'What to apply for this week, which documents to collect, and every deadline in your calendar.'))}</p></li>
        </ol>
      </section>

      <section class="band" id="features" aria-labelledby="pillarsTitle">
        <div class="band-head reveal"><h2 class="h1" id="pillarsTitle">${esc(t('land.pillarsT', 'Two things that change your year'))}</h2>
          <p class="lede">${esc(t('land.pillarsP', 'Money you are entitled to, and work you can get. LifePilot does both.'))}</p></div>
        <div class="pillars">
          <article class="card card-lift pillar reveal">
            <span class="pillar-icon s">${icon('landmark', 'icon-lg')}</span>
            <h3 class="h1">${esc(t('nav.schemes', 'Schemes'))}</h3>
            <ul>
              <li>${icon('check')}<span>${esc(t('land.sch1', 'A clear verdict for every scholarship and scheme, with the reasons'))}</span></li>
              <li>${icon('check')}<span>${esc(t('land.sch2', '“What if” simulator: see what changes if your income or studies change'))}</span></li>
              <li>${icon('check')}<span>${esc(t('land.sch3', 'Deadlines on a timeline, and in your calendar in one click'))}</span></li>
            </ul>
            <div class="preview" aria-hidden="true">
              <div class="row" style="justify-content:space-between"><div><p style="font-weight:650">AICTE Pragati Scholarship</p><p class="tiny quiet">₹50,000 / year</p></div>${stamp('eligible')}</div>
            </div>
          </article>
          <article class="card card-lift pillar reveal">
            <span class="pillar-icon j">${icon('briefcase', 'icon-lg')}</span>
            <h3 class="h1">${esc(t('nav.jobs', 'Jobs'))}</h3>
            <ul>
              <li>${icon('check')}<span>${esc(t('land.job1b', 'Live openings from LinkedIn, Naukri, Indeed and company sites, your state first'))}</span></li>
              <li>${icon('check')}<span>${esc(t('land.job2b', 'Reads your resume and gives each job a fit score learned by ML, with how it was made'))}</span></li>
              <li>${icon('check')}<span>${esc(t('land.job3b', 'A week-by-week roadmap for any job, shaped by the hours you have'))}</span></li>
            </ul>
            <div class="preview" aria-hidden="true">
              <div class="row" style="justify-content:space-between;margin-bottom:10px"><p style="font-weight:650">Backend developer</p><b class="num">78%</b></div>
              <div class="meter"><span class="seg-must" style="width:30%"></span><span class="seg-role" style="width:24%"></span><span class="seg-experience" style="width:14%"></span><span class="seg-education" style="width:10%"></span></div>
              <div class="skills"><span class="skill">${icon('check', 'icon-sm')}Python</span><span class="skill">${icon('check', 'icon-sm')}SQL</span><span class="skill missing">Redis</span></div>
            </div>
          </article>
        </div>
      </section>

      <section class="band" aria-labelledby="featT">
        <div class="band-head reveal"><h2 class="h1" id="featT">${esc(t('land.featT', 'Everything in one place'))}</h2></div>
        <div class="features bento">
          ${[
            ['scan-line', 'land.c2', 'Document scanner', 'land.c2p', 'Photograph a certificate. LifePilot reads it in your browser, checks it against your profile and ticks your checklist.', 'scan'],
            ['list-todo', 'land.c3', 'Smart priority planner', 'land.c3p', 'Deadlines, amounts and missing documents turned into the best order to apply, week by week.', 'plan'],
            ['network', 'land.c5', 'Scheme map', 'land.c5p', 'See how one document unlocks several schemes at once.', 'map'],
            ['mic', 'land.c4', 'Voice in Hindi and English', 'land.c4p', 'Speak your question and hear the answer.', 'voice'],
            ['message-circle', 'land.f1', 'Ask the assistant', 'land.f1p', 'Ask in plain words about your schemes, documents or deadlines. Answers use your own results.'],
            ['wand-sparkles', 'land.c6', '“What would change it?”', 'land.c6p', 'The smallest change that would unlock more schemes or jobs for you.'],
            ['sliders-horizontal', 'land.f3', 'What-if simulator', 'land.f3p', 'Move the income slider or change category and watch your results change instantly.'],
            ['route', 'land.c1', 'Personal job roadmaps', 'land.c1p', 'A week-by-week plan for each job: skills in the right order, free courses, a project to build.'],
            ['folder-check', 'land.f2', 'Document checklist', 'land.f2p', 'One list of every document your schemes need. Keep copies in your browser, never uploaded.'],
            ['wand-sparkles', 'land.f5', 'Describe yourself in one line', 'land.f5p', 'Type one sentence in Hindi or English and the form fills itself.'],
            ['bot', 'land.f6', 'ML Lab', 'land.f6p', 'Six machine learning models with their real accuracy, and a box to try each one.'],
            ['calendar-plus', 'land.f7', 'Deadlines in your calendar', 'land.f7p', 'Add every deadline to your phone calendar, or print your action plan.'],
          ].map(([ic, k, en, kp, enp, art]) => `<article class="card feature ${art ? `feature-wide feature-${art}` : ''} reveal">
            ${art ? `<div class="feature-art" aria-hidden="true">${ART[art]}</div>` : ''}
            <span class="feature-icon">${icon(ic)}</span><h3 class="h3">${esc(t(k, en))}</h3><p>${esc(t(kp, enp))}</p></article>`).join('')}
        </div>
      </section>

      <section class="band" aria-labelledby="trustT">
        <h2 class="sr-only" id="trustT">${esc(t('land.trustT', 'Why you can trust it'))}</h2>
        <div class="trust ink reveal"><div class="trust-rosette">${rosette()}</div>
          <div>${icon('scale')}<h3 class="h3">${esc(t('land.t1', 'Rules decide, not AI'))}</h3><p class="small quiet">${esc(t('land.t1p', 'Eligibility comes from each scheme’s published rules. AI never overrules them.'))}</p></div>
          <div>${icon('shield-check')}<h3 class="h3">${esc(t('land.t2', 'Your files stay with you'))}</h3><p class="small quiet">${esc(t('land.t2p', 'Documents are kept in your browser and never uploaded.'))}</p></div>
          <div>${icon('wifi-off')}<h3 class="h3">${esc(t('land.t3', 'Works offline'))}</h3><p class="small quiet">${esc(t('land.t3p', 'Nothing loads from outside sites, so it runs even on a weak connection.'))}</p></div>
          <div>${icon('heart-handshake')}<h3 class="h3">${esc(t('land.t4', 'Free'))}</h3><p class="small quiet">${esc(t('land.t4p', 'No fees, no ads, no paid AI keys needed.'))}</p></div>
        </div>
      </section>

      <section class="band" aria-labelledby="ctaT">
        <div class="card cta-final reveal"><div class="cta-rosette">${rosette()}</div>
          <h2 class="h1" id="ctaT">${esc(has ? t('land.ctaHas', 'Your plan is waiting') : t('land.ctaT', 'Ready to see what you qualify for?'))}</h2>
          ${has ? startBtn : `<div class="signin-choices">
            <div><h3 class="h3">${esc(t('land.guestT', 'Continue without an account'))}</h3><p class="small quiet">${esc(t('land.guestP', 'Fastest way to start. Your profile is linked to this browser.'))}</p>
              <a class="btn btn-primary" href="#/start">${esc(t('land.start', 'Get started free'))}${icon('arrow-right', 'arrow')}</a></div>
            <div><h3 class="h3">${esc(t('land.acctT', 'Sign in'))}</h3><p class="small quiet">${esc(t('land.acctP', 'Keep your profile on every device. Anything you started as a guest is kept.'))}</p>
              <button class="btn btn-secondary" type="button" data-signin>${icon('log-in')}${esc(t('auth.signin', 'Sign in'))}</button></div>
          </div>`}
        </div>
      </section>

      <footer class="footer"><span class="foot-brand">${logoMark()}<b>LifePilot</b></span><span>${esc(t('land.foot', 'Scholarships, schemes and jobs, checked against your profile.'))}</span></footer>
    </div>`;

    el.querySelectorAll('[data-signin]').forEach((b) => b.addEventListener('click', signIn));
    el.querySelector('#tryExample')?.addEventListener('click', () => { startWithExample(); location.hash = '#/start'; });
    reveal(el);
    splitWords(el.querySelector('.hero-title'));
    requestAnimationFrame(() => el.querySelector('.hero-ink')?.classList.add('play'));
    flyPlane(el);

    // Cycling headline word
    const cyc = el.querySelectorAll('.cycle > span');
    let w = 0;
    const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (!reduce) timers.push(setInterval(() => {
      if (!document.body.contains(el.querySelector('.cycle'))) return clearTimers();
      cyc[w].classList.replace('on', 'out');
      const prev = cyc[w];
      w = (w + 1) % cyc.length;
      cyc[w].classList.remove('out'); cyc[w].classList.add('on');
      setTimeout(() => prev.classList.remove('out'), 650);
    }, 2400));

    // Live demo: rotate sample students, pause while the user is reading
    let i = 0, paused = false;
    showSample(el, 0);
    const demo = el.querySelector('.demo');
    demo.addEventListener('mouseenter', () => { paused = true; });
    demo.addEventListener('mouseleave', () => { paused = false; });
    demo.addEventListener('focusin', () => { paused = true; });
    el.querySelectorAll('[data-sample]').forEach((b) => b.addEventListener('click', () => { i = +b.dataset.sample; showSample(el, i); }));
    if (!reduce) timers.push(setInterval(() => {
      if (!document.body.contains(demo)) return clearTimers();
      if (paused || document.hidden) return;
      i = (i + 1) % SAMPLES.length; showSample(el, i);
    }, 5200));

  },
  leave: clearTimers,
};
