/* App state with tiny pub/sub. Per-browser conveniences are kept in localStorage. */
import { store, matchStatus } from './util.js';

const listeners = new Set();

export const state = {
  profileId: store.get('lp_pid'),
  profile: store.get('lp_profile'),
  run: null,              // latest agent run: { matches, logs, insights, summary }
  running: false,
  runError: null,
  user: null,             // signed-in user, if any
  ownedDocs: new Set(store.get('lp_docs', [])),
  vault: {},              // key -> { name, size } for files kept in IndexedDB
  jobs: store.get('lp_jobs', null),   // { query, results, at }
  health: null,
};

/** Listeners receive (state, changedKeys) so pages re-render only for what they show. */
export function setState(patch) {
  Object.assign(state, patch);
  const keys = Object.keys(patch);
  listeners.forEach((fn) => fn(state, keys));
}

export const subscribe = (fn) => { listeners.add(fn); return () => listeners.delete(fn); };

export function saveProfile(id, profile) {
  state.profileId = id;
  state.profile = profile;
  store.set('lp_pid', id);
  store.set('lp_profile', profile);
}

export function forgetProfile() {
  state.profileId = null; state.profile = null; state.run = null; state.jobs = null;
  store.remove('lp_pid', 'lp_profile', 'lp_pkey', 'lp_jobs');
  try {
    Object.keys(localStorage).filter((k) => k.startsWith('lp_plan_')).forEach((k) => localStorage.removeItem(k));
    sessionStorage.removeItem('lp_resume');
  } catch { /* storage blocked */ }
}

export const saveDocs = () => store.set('lp_docs', [...state.ownedDocs]);
export function saveJobs(jobs) { state.jobs = jobs; store.set('lp_jobs', jobs); }

export const hasDoc = (name) => {
  const k = name.toLowerCase().trim();
  return state.ownedDocs.has(k) || !!state.vault[k];
};

export const eligibleMatches = () => (state.run?.matches || []).filter((m) => matchStatus(m) === 'eligible');

/** Documents for the schemes you qualify for (falls back to every open scheme
 *  when you qualify for none), each with the schemes it is needed by. */
export function readiness() {
  const elig = eligibleMatches();
  let docs;
  if (elig.length) {
    const map = new Map();
    for (const m of elig) {
      for (const d of m.documents || []) {
        const k = d.toLowerCase().trim();
        if (!map.has(k)) map.set(k, { document: d, schemes: [] });
        map.get(k).schemes.push(m.title);
      }
    }
    docs = [...map.values()].map((d) => ({ ...d, used_by: d.schemes.length }))
      .sort((a, b) => b.used_by - a.used_by || a.document.localeCompare(b.document));
  } else {
    docs = state.run?.insights?.master_documents || [];
  }
  const owned = docs.filter((d) => hasDoc(d.document)).length;
  return { docs, total: docs.length, owned, pct: docs.length ? Math.round((100 * owned) / docs.length) : 0 };
}
