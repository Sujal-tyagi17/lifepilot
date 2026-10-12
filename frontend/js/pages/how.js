/* How it works: the agent trace for your last run, for anyone who wants to see the reasoning. */
import { esc } from '../util.js';
import { t } from '../i18n.js';
import { icon } from '../ui.js';
import { emptyCard } from '../components.js';
import { state } from '../state.js';

const ROLE = {
  PlannerAgent: 'Reads your profile and plans what to look for',
  ResearchAgent: 'Collects schemes from the curated list (and the web, if enabled)',
  EligibilityAgent: 'Checks every rule of every scheme against your profile',
  DocumentAgent: 'Builds one list of the documents those schemes need',
  TrackingAgent: 'Sorts deadlines by how soon they close',
  RoadmapAgent: 'Writes the steps to apply for each scheme',
};

export const how = {
  title: () => t('nav.how', 'How it works'),
  sub: () => t('how.lede', 'What each agent did in your last check, in order.'),
  deps: ['run'],
  render(el) {
    const logs = state.run?.logs || [];
    el.innerHTML = `
      <p class="notice">${icon('info')}<span>${esc(t('how.rules', 'Eligibility is decided by rules, not by AI. Every verdict shows its reasons.'))}</span></p>
      <a class="card card-lift panel-pad ml-link" href="#/ml-lab">${icon('bot')}<span><b>${esc(t('ml.title', 'ML Lab'))}</b><br><span class="small quiet">${esc(t('how.mlLink', 'The six machine learning models: their data, accuracy, and a box to try each one.'))}</span></span>${icon('arrow-right')}</a>
      ${logs.length ? `<section class="card section" style="margin-top:18px"><ol class="trace">${logs.map((l, i) => `
        <li>
          <span class="trace-step num" aria-hidden="true">${i + 1}</span>
          <div><p style="font-weight:640">${esc(l.agent)}</p>
            ${ROLE[l.agent] ? `<p class="small quiet">${esc(ROLE[l.agent])}</p>` : ''}
            <p class="small" style="margin-top:4px">${esc(l.message)}</p></div>
          ${l.confidence != null ? `<span class="small quiet num">${esc(t('how.confidence', 'Confidence {pct}%', { pct: Math.round(l.confidence * 100) }))}</span>` : ''}
        </li>`).join('')}</ol></section>`
        : `<div class="section">${emptyCard({ iconName: 'route', title: t('how.empty', 'No check has run yet.') })}</div>`}`;
  },
};
