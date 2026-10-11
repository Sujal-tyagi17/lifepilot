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

// Fictional sample students. Their results are computed live by the rule engine.
const SAMPLES = [
  { initials: 'AK', name: 'Aisha, 21', facts: ['B.Tech', 'OBC', 'Karnataka', '₹3 lakh/yr'],
    profile: { name: 'Aisha', age: 21, gender: 'Female', state: 'Karnataka', category: 'OBC', education_level: 'Undergraduate', field_of_study: 'Engineering', annual_income: 300000, goals: 'start a company' } },
  { initials: 'RK', name: 'Rohan, 17', facts: ['Class 12', 'SC', 'Bihar', '₹1.8 lakh/yr'],
    profile: { name: 'Rohan', age: 17, gender: 'Male', state: 'Bihar', category: 'SC', education_level: '12th', field_of_study: 'Science', annual_income: 180000 } },
  { initials: 'MP', name: 'Meera, 23', facts: ['M.Sc Physics', 'General', 'Maharashtra', '₹4 lakh/yr'],
    profile: { name: 'Meera', age: 23, gender: 'Female', state: 'Maharashtra', category: 'General', education_level: 'Postgraduate', field_of_study: 'Physics', annual_income: 400000 } },
];

const WORDS = () => [t('land.w1', 'scholarships'), t('land.w2', 'schemes'), t('land.w3', 'jobs')];

let timers = [];
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

export const landing = {
  title: () => '',
  full: true,
  render(el) {
    clearTimers();
    const has = !!state.profileId;
    const startBtn = has
      ? `<a class="btn btn-primary btn-lg" href="#/home">${esc(t('land.open', 'Open my dashboard'))}${icon('arrow-right', 'arrow')}</a>`
      : `<a class="btn btn-primary btn-lg" href="#/start">${esc(t('land.start', 'Get started free'))}${icon('arrow-right', 'arrow')}</a>`;
    const words = WORDS();
    el.innerHTML = `
    <div class="wrap">
      <section class="hero" aria-labelledby="heroTitle">
        <div>
          <span class="badge"><span class="dot">${icon('check', 'icon-sm')}</span>${esc(t('land.badge', 'Free · Hindi and English · Works offline'))}</span>
          <h1 class="hero-title" id="heroTitle">${esc(t('land.h1a', 'Find the'))}<br />
            <span class="cycle" aria-hidden="true">${words.map((w, i) => `<span class="${i === 0 ? 'on' : ''}">${esc(w)}</span>`).join('')}</span><br />
            ${esc(t('land.h1b', 'you qualify for.'))}
            <span class="sr-only">${esc(words.join(', '))}</span></h1>
          <p class="hero-lede">${esc(t('land.lede', 'LifePilot checks every rule of every scheme against your profile, matches jobs to your resume, and turns it into a plan: what to apply for, which documents to get, and what to learn next.'))}</p>
          <div class="hero-ctas">
            ${startBtn}
            ${state.user ? '' : `<button class="btn btn-secondary btn-lg" type="button" data-signin>${icon('log-in')}${esc(t('auth.signin', 'Sign in'))}</button>`}
            ${has ? '' : `<button class="btn btn-quiet btn-lg" type="button" id="tryExample">${icon('play')}${esc(t('land.example', 'Try a sample profile'))}</button>`}
          </div>
          <p class="hero-note">
            <span>${icon('check', 'icon-sm')}${esc(t('land.n1', 'No account needed'))}</span>
            <span>${icon('check', 'icon-sm')}${esc(t('land.n2', 'About 2 minutes'))}</span>
            <span>${icon('check', 'icon-sm')}${esc(t('land.n3', 'Documents never leave your device'))}</span>
          </p>
        </div>

        <div class="demo" aria-label="${esc(t('land.demo', 'Live preview'))}">
          <div class="float glass float-1">${icon('scale')}<span>${esc(t('land.float1', 'Rules decide, not guesses'))}</span></div>
          <div class="float glass float-2">${icon('calendar-clock')}<span id="floatDeadline">${esc(t('land.floatRules', 'Every rule checked'))}</span></div>
          <div class="float glass float-3">${icon('languages')}<span>हिन्दी · English</span></div>
          <div class="card demo-card" id="demoCard">
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
      </section>

      <section class="band" id="how" aria-labelledby="howTitle">
        <div class="band-head reveal"><h2 class="h1" id="howTitle">${esc(t('land.howT', 'From “am I eligible?” to a plan in three steps'))}</h2></div>
        <ol class="steps3">
          <li class="card card-lift reveal"><h3 class="h2">${esc(t('land.s1', 'Tell us about you'))}</h3><p>${esc(t('land.s1p', 'One question at a time: studies, family income, category, state. Skip anything you are unsure of.'))}</p></li>
          <li class="card card-lift reveal"><h3 class="h2">${esc(t('land.s2', 'We check every rule'))}</h3><p>${esc(t('land.s2p', 'Each scheme’s rules are checked one by one. You see exactly why you qualify, or what is missing.'))}</p></li>
          <li class="card card-lift reveal"><h3 class="h2">${esc(t('land.s3', 'Get your plan'))}</h3><p>${esc(t('land.s3p', 'What to apply for this week, which documents to collect, and every deadline in your calendar.'))}</p></li>
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
        <div class="features">
          ${[
            ['message-circle', 'land.f1', 'Ask the assistant', 'land.f1p', 'Ask in plain words about your schemes, documents or deadlines. Answers use your own results.'],
            ['folder-check', 'land.f2', 'Document checklist', 'land.f2p', 'One list of every document your schemes need. Keep copies in your browser, never uploaded.'],
            ['sliders-horizontal', 'land.f3', 'What-if simulator', 'land.f3p', 'Move the income slider or change category and watch your results change instantly.'],
            ['route', 'land.c1', 'Personal job roadmaps', 'land.c1p', 'A week-by-week plan for each job: skills in the right order, free courses, a project to build.'],
            ['wand-sparkles', 'land.f5', 'Describe yourself in one line', 'land.f5p', 'Type one sentence in Hindi or English and the form fills itself.'],
            ['bot', 'land.f6', 'ML Lab', 'land.f6p', 'Six machine learning models with their real accuracy, and a box to try each one.'],
          ].map(([ic, k, en, kp, enp]) => `<article class="card card-lift feature reveal"><span class="feature-icon">${icon(ic)}</span><h3 class="h3">${esc(t(k, en))}</h3><p>${esc(t(kp, enp))}</p></article>`).join('')}
          ${[
            ['scan-line', 'land.c2', 'Document scanner', 'land.c2p', 'Photograph a certificate. LifePilot reads it, ticks your checklist and warns if it has expired.'],
            ['list-todo', 'land.c3', 'Smart priority planner', 'land.c3p', 'Deadlines, amounts and missing documents turned into the best order to apply.'],
            ['mic', 'land.c4', 'Voice in Hindi and English', 'land.c4p', 'Speak your question and hear the answer.'],
            ['network', 'land.c5', 'Scheme map', 'land.c5p', 'See how one document unlocks several schemes at once.'],
            ['wand-sparkles', 'land.c6', '“What would change it?”', 'land.c6p', 'The smallest change that would unlock more schemes or jobs for you.'],
          ].map(([ic, k, en, kp, enp]) => `<article class="card feature is-soon reveal"><span class="soon-badge">${esc(t('land.soon', 'Coming next'))}</span><span class="feature-icon">${icon(ic)}</span><h3 class="h3">${esc(t(k, en))}</h3><p>${esc(t(kp, enp))}</p></article>`).join('')}
        </div>
      </section>

      <section class="band" aria-labelledby="trustT">
        <h2 class="sr-only" id="trustT">${esc(t('land.trustT', 'Why you can trust it'))}</h2>
        <div class="trust card reveal">
          <div>${icon('scale')}<h3 class="h3">${esc(t('land.t1', 'Rules decide, not AI'))}</h3><p class="small quiet">${esc(t('land.t1p', 'Eligibility comes from each scheme’s published rules. AI never overrules them.'))}</p></div>
          <div>${icon('shield-check')}<h3 class="h3">${esc(t('land.t2', 'Your files stay with you'))}</h3><p class="small quiet">${esc(t('land.t2p', 'Documents are kept in your browser and never uploaded.'))}</p></div>
          <div>${icon('wifi-off')}<h3 class="h3">${esc(t('land.t3', 'Works offline'))}</h3><p class="small quiet">${esc(t('land.t3p', 'Nothing loads from outside sites, so it runs even on a weak connection.'))}</p></div>
          <div>${icon('heart-handshake')}<h3 class="h3">${esc(t('land.t4', 'Free'))}</h3><p class="small quiet">${esc(t('land.t4p', 'No fees, no ads, no paid AI keys needed.'))}</p></div>
        </div>
      </section>

      <section class="band" aria-labelledby="ctaT">
        <div class="card cta-final reveal">
          <h2 class="h1" id="ctaT">${esc(has ? t('land.ctaHas', 'Your plan is waiting') : t('land.ctaT', 'Ready to see what you qualify for?'))}</h2>
          ${has ? startBtn : `<div class="signin-choices">
            <div><h3 class="h3">${esc(t('land.guestT', 'Continue without an account'))}</h3><p class="small quiet">${esc(t('land.guestP', 'Fastest way to start. Your profile is linked to this browser.'))}</p>
              <a class="btn btn-primary" href="#/start">${esc(t('land.start', 'Get started free'))}${icon('arrow-right', 'arrow')}</a></div>
            <div><h3 class="h3">${esc(t('land.acctT', 'Sign in'))}</h3><p class="small quiet">${esc(t('land.acctP', 'Keep your profile on every device. Anything you started as a guest is kept.'))}</p>
              <button class="btn btn-secondary" type="button" data-signin>${icon('log-in')}${esc(t('auth.signin', 'Sign in'))}</button></div>
          </div>`}
        </div>
      </section>

      <footer class="footer"><span>LifePilot</span><span>${esc(t('land.foot', 'Scholarships, schemes and jobs, checked against your profile.'))}</span></footer>
    </div>`;

    el.querySelectorAll('[data-signin]').forEach((b) => b.addEventListener('click', signIn));
    el.querySelector('#tryExample')?.addEventListener('click', () => { startWithExample(); location.hash = '#/start'; });
    reveal(el);

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

    // Gentle tilt of the demo card toward the pointer
    if (!reduce && matchMedia('(pointer: fine)').matches) {
      const card = el.querySelector('#demoCard');
      demo.addEventListener('mousemove', (e) => {
        const r = demo.getBoundingClientRect();
        const x = (e.clientX - r.left) / r.width - .5, y = (e.clientY - r.top) / r.height - .5;
        card.style.transform = `perspective(1000px) rotateY(${x * 5}deg) rotateX(${-y * 5}deg)`;
      });
      demo.addEventListener('mouseleave', () => { card.style.transform = ''; });
    }
  },
  leave: clearTimers,
};
