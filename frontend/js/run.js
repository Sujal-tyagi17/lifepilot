/* Running the agent pipeline and loading saved results. */
import { api, auth, ApiError } from './api.js';
import { state, setState, saveProfile, forgetProfile } from './state.js';
import { t } from './i18n.js';

function handleGone(err) {
  // Saved before profiles were protected, or deleted on another device.
  if (err instanceof ApiError && err.status === 404) {
    forgetProfile();
    setState({ run: null, profileId: null, profile: null });
    location.hash = '#/welcome';
    return new Error(t('profile.again', 'Please save your profile again to continue.'));
  }
  return err;
}

/** Saved results for this profile, without re-running anything. */
export async function loadLatest() {
  if (!state.profileId) return null;
  try {
    const run = await api(`/api/agent/latest/${state.profileId}`);
    if (run) setState({ run });
    return run;
  } catch (err) {
    throw handleGone(err);
  }
}

/** Run the full pipeline (may call web search and the LLM, so it can take a while). */
export async function runAgents() {
  if (!state.profileId || state.running) return null;
  setState({ running: true, runError: null });
  try {
    const run = await api(`/api/agent/run/${state.profileId}`, { method: 'POST' });
    setState({ run, running: false });
    return run;
  } catch (err) {
    const e = handleGone(err);
    setState({ running: false, runError: e.message });
    throw e;
  }
}

/** Create or update the profile, then run the pipeline.
 *  `onSaved` runs once the profile exists (e.g. to open Home while matching runs). */
export async function saveAndRun(profile, onSaved) {
  const saved = await api('/api/profiles', { method: 'POST', json: profile });
  auth.profileKey = saved.guest_key;
  saveProfile(saved.id, { ...profile, id: saved.id });
  setState({ profileId: saved.id, profile: state.profile });
  const running = runAgents();
  onSaved?.();
  return running;
}

export function simulate(profile) {
  return api('/api/agent/simulate', { method: 'POST', json: { ...profile, owned_documents: [] } });
}
