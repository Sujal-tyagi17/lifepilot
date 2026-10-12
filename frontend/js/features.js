/* Phase 4 API calls with a small cache: what would change it, the planner,
   the knowledge graph and the document check. */
import { api } from './api.js';
import { state } from './state.js';
import { store } from './util.js';

const cache = new Map();

/** Every document the person has ticked or kept a file for. */
export const ownedDocuments = () => [...new Set([...state.ownedDocs, ...Object.keys(state.vault || {})])];

const runKey = () => `${state.profileId}:${state.run?.id ?? ''}`;

async function cached(key, fn) {
  if (cache.has(key)) return cache.get(key);
  const p = fn().catch((err) => { cache.delete(key); throw err; });
  cache.set(key, p);
  return p;
}

export function counterfactuals() {
  return cached(`cf:${runKey()}`, () => api(`/api/counterfactuals/${state.profileId}`));
}

export function knowledgeGraph() {
  const owned = ownedDocuments().sort();
  return cached(`graph:${runKey()}:${owned.join('|')}`, () =>
    api(`/api/graph/${state.profileId}`, { method: 'POST', json: { owned_documents: owned } }));
}

export const planHours = {
  get: () => Number(store.get('lp_plan_hours', 6)) || 6,
  set: (h) => store.set('lp_plan_hours', h),
};

/** Best live jobs from the last Jobs search, and the best next skill. */
function planJobs() {
  const rep = state.jobs?.report;
  if (!rep) return { jobs: [], skill: null };
  const jobs = (rep.jobs || []).filter((j) => j.source !== 'sample' && j.relevant && !j.too_senior)
    .sort((a, b) => b.fit_score - a.fit_score).slice(0, 6)
    .map((j) => ({ id: String(j.id ?? j.url ?? j.title), title: j.title, company: j.company || null, url: j.url || null, fit_score: j.fit_score }));
  const skill = rep.insight ? { skill: rep.insight.skill, jobs: rep.insight.jobs } : null;
  return { jobs, skill };
}

export function priorityPlan(hours = planHours.get()) {
  const owned = ownedDocuments().sort();
  const { jobs, skill } = planJobs();
  const key = `plan:${runKey()}:${hours}:${owned.join('|')}:${jobs.map((j) => j.id).join('|')}`;
  return cached(key, () => api(`/api/planner/${state.profileId}`, {
    method: 'POST', json: { hours_per_week: hours, owned_documents: owned, jobs, skill },
  }));
}

export function verifyDocument(text) {
  return api('/api/documents/verify', { method: 'POST', json: { text, profile_id: state.profileId || null } });
}
