/* Sign-in with Kinde (or the offline demo account when Kinde is not configured). */
import { api, auth } from './api.js';
import { state, setState, saveProfile, forgetProfile } from './state.js';
import { store } from './util.js';

export async function initAuth() {
  const params = new URLSearchParams(location.search);
  const code = params.get('code');
  if (code) {
    history.replaceState({}, document.title, location.pathname + location.hash);
    try {
      const res = await api('/api/auth/exchange', { method: 'POST', json: { code, redirect_uri: location.origin } });
      if (res?.access_token) {
        auth.token = res.access_token;
        setState({ user: res.user });
      }
    } catch (err) {
      console.warn('Sign-in failed:', err.message);
    }
  } else if (auth.token) {
    try {
      const me = await api('/api/auth/me');
      if (me?.authenticated) setState({ user: me.user });
      else auth.token = null;
    } catch {
      auth.token = null;
    }
  }

  if (state.user) {
    // A guest profile made before signing in is claimed by the server (it sends the guest key).
    try {
      const saved = await api('/api/profiles/me/latest');
      if (saved?.id) {
        auth.profileKey = saved.guest_key;
        saveProfile(saved.id, saved);
        setState({ profileId: saved.id, profile: saved });
      }
    } catch { /* keep any guest profile */ }
  }
}

export const signIn = () => { location.href = '/api/auth/login'; };

export function signOut() {
  auth.token = null;
  forgetProfile();
  location.href = '/api/auth/logout';
}

/** Delete everything: the account (signed in) or the guest profile, plus local files. */
export async function deleteEverything(clearVault) {
  if (state.user) {
    const res = await api('/api/auth/account', { method: 'DELETE' });
    await clearVault();
    auth.token = null;
    forgetProfile();
    store.remove('lp_docs');
    location.href = res?.logout_url || '/';
    return;
  }
  if (state.profileId) {
    try { await api(`/api/profiles/${state.profileId}`, { method: 'DELETE' }); } catch { /* already gone */ }
  }
  await clearVault();
  forgetProfile();
  store.remove('lp_docs');
  state.ownedDocs.clear();
  setState({ run: null, profileId: null, profile: null, vault: {} });
}
