/* Same-origin JSON API client. Sends the login token (if signed in) and the
   guest profile key (see backend/app/ownership.py) with every request. */
import { store } from './util.js';
import { t } from './i18n.js';

const TOKEN_KEY = 'lifepilot_auth_token';
const PROFILE_KEY = 'lp_pkey';

export const auth = {
  get token() { return store.raw(TOKEN_KEY); },
  set token(v) { store.setRaw(TOKEN_KEY, v); },
  get profileKey() { return store.raw(PROFILE_KEY); },
  set profileKey(v) { if (v) store.setRaw(PROFILE_KEY, v); },
  clearProfileKey() { store.remove(PROFILE_KEY); },
};

export class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}

export async function api(path, { method = 'GET', json, body, headers = {}, timeout = 0 } = {}) {
  const h = { ...headers };
  if (auth.token) h.Authorization = `Bearer ${auth.token}`;
  if (auth.profileKey) h['X-Profile-Key'] = auth.profileKey;
  if (json !== undefined) { h['Content-Type'] = 'application/json'; body = JSON.stringify(json); }
  let r;
  const ctrl = timeout ? new AbortController() : null;
  const timer = ctrl && setTimeout(() => ctrl.abort(), timeout);
  try {
    r = await fetch(path, { method, headers: h, body, signal: ctrl?.signal });
  } catch {
    if (ctrl?.signal.aborted) throw new ApiError(t('err.timeout', 'The server took too long to answer. Try again in a moment.'), 0);
    throw new ApiError(t('err.network', 'Could not reach the server. Check that LifePilot is running.'), 0);
  } finally {
    if (timer) clearTimeout(timer);
  }
  if (!r.ok) {
    let detail = r.statusText;
    try { detail = (await r.json()).detail || detail; } catch { /* not JSON */ }
    throw new ApiError(typeof detail === 'string' ? detail : JSON.stringify(detail), r.status);
  }
  return r.status === 204 ? null : r.json();
}
