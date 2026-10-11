/* Assistant: a drawer available on every page. Answers come from your saved results. */
import { $, esc } from './util.js';
import { t } from './i18n.js';
import { icon } from './ui.js';
import { api } from './api.js';
import { state } from './state.js';
import { canListen, canSpeak, listen, stopListening, listening, speak, stopSpeaking, speakOn, voiceLang } from './voice.js';

const log = [];   // { who: 'user' | 'bot', text, intent }

const INTENT_NAMES = {
  eligibility: ['int.eligibility', 'Eligibility'], documents: ['int.documents', 'Documents'], deadlines: ['int.deadlines', 'Deadlines'],
  benefits: ['int.benefits', 'Benefits'], how_to_apply: ['int.apply', 'How to apply'], jobs: ['int.jobs', 'Jobs'], other: ['int.other', 'General'],
};

/** Safe, tiny Markdown: **bold**, bullet lines and links. Everything is escaped first. */
function md(text) {
  const lines = esc(text || '').split('\n');
  let html = '', inList = false;
  for (const raw of lines) {
    let line = raw.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
      .replace(/(^|[\s(])(https?:\/\/[^\s<)]+[^\s<).,])/g, '$1<a href="$2" target="_blank" rel="noopener noreferrer">$2</a>');
    const bullet = /^\s*(?:[•*-]|\d+\.)\s+/.test(raw);
    if (bullet) {
      if (!inList) { html += '<ul>'; inList = true; }
      html += `<li>${line.replace(/^\s*(?:[•*-]|\d+\.)\s+/, '')}</li>`;
    } else {
      if (inList) { html += '</ul>'; inList = false; }
      if (line.trim()) html += `<p>${line}</p>`;
    }
  }
  return html + (inList ? '</ul>' : '');
}

function intentBadge(it) {
  if (!it || !it.label) return '';
  const [k, en] = INTENT_NAMES[it.label] || INTENT_NAMES.other;
  const how = it.by === 'model' ? t('int.byModel', 'ML intent classifier, {p}% sure', { p: Math.round((it.confidence || 0) * 100) }) : t('int.byKeywords', 'matched by keywords');
  return `<span class="intent-badge" title="${esc(how)}">${icon('sparkle', 'icon-sm')}${esc(t(k, en))}</span>`;
}
let lastFocus = null;

const SUGGEST = [['asst.q4', 'Which schemes do I qualify for?'], ['asst.q2', 'What documents do I need?'], ['asst.q3', 'When are the deadlines?'], ['asst.q1', 'How much can I get?']];

function render() {
  const d = $('#drawer');
  d.innerHTML = `
    <div class="drawer-head">
      <span class="bot-face" aria-hidden="true">${icon('sparkles')}</span>
      <div style="flex:1"><h2 class="h3" id="drawerTitle">${esc(t('asst.title', 'Assistant'))}</h2>
        <p class="tiny quiet">${esc(t('asst.lede', 'Answers based on your real matches'))}</p></div>
      ${canSpeak() ? `<button class="btn btn-quiet btn-icon" type="button" id="speakBtn" aria-pressed="${speakOn.get()}" aria-label="${esc(t('voice.speak', 'Read answers aloud'))}" title="${esc(t('voice.speak', 'Read answers aloud'))}">${icon(speakOn.get() ? 'volume-2' : 'volume-x')}</button>` : ''}
      <button class="btn btn-quiet btn-icon" type="button" id="drawerClose" aria-label="${esc(t('asst.close', 'Close'))}">${icon('x')}</button>
    </div>
    <div class="chat-log" id="chatLog" aria-live="polite">
      ${[{ who: 'bot', text: state.profileId ? t('asst.hello', 'Hello! Ask about your schemes, documents or deadlines.') : t('asst.needProfile', 'Fill in your profile first, then I can answer about your matches.') }, ...log]
        .map((m) => m.typing
          ? `<p class="bubble bot" aria-label="…"><span class="typing"><i></i><i></i><i></i></span></p>`
          : m.who === 'bot'
            ? `<div class="bubble bot">${m.intent ? intentBadge(m.intent) : ''}${md(m.text)}</div>`
            : `<p class="bubble ${m.who}">${esc(m.text)}</p>`).join('')}
    </div>
    ${state.profileId && log.length < 2 ? `<div class="chat-suggest">${SUGGEST.map(([k, en]) => `<button class="chip-btn" type="button" data-q="${esc(t(k, en))}">${esc(t(k, en))}</button>`).join('')}</div>` : ''}
    <form class="chat-form" id="chatForm">
      <label class="sr-only" for="chatInput">${esc(t('asst.ph', 'Ask about eligibility, documents, deadlines'))}</label>
      <input class="input" id="chatInput" autocomplete="off" maxlength="500" placeholder="${esc(t('asst.ph', 'Ask about eligibility, documents, deadlines'))}" ${state.profileId ? '' : 'disabled'} />
      ${canListen() ? `<button class="btn btn-secondary btn-icon mic-btn" type="button" id="micBtn" aria-pressed="false" aria-label="${esc(t('voice.mic', 'Speak your question ({lang})', { lang: voiceLang() === 'hi-IN' ? 'हिन्दी' : 'English' }))}" title="${esc(t('voice.micTip', 'Speak in {lang}. Your browser sends the audio to its speech service to turn it into text.', { lang: voiceLang() === 'hi-IN' ? 'हिन्दी' : 'English' }))}" ${state.profileId ? '' : 'disabled'}>${icon('mic')}</button>` : ''}
      <button class="btn btn-primary btn-icon" type="submit" aria-label="${esc(t('asst.send', 'Send'))}" ${state.profileId ? '' : 'disabled'}>${icon('send')}</button>
    </form>`;
  const chat = $('#chatLog'); chat.scrollTop = chat.scrollHeight;
  $('#drawerClose').addEventListener('click', closeAssistant);
  d.querySelectorAll('[data-q]').forEach((b) => b.addEventListener('click', () => ask(b.dataset.q)));
  $('#chatForm').addEventListener('submit', (e) => { e.preventDefault(); ask($('#chatInput').value); });
  $('#speakBtn')?.addEventListener('click', () => {
    speakOn.set(!speakOn.get());
    if (!speakOn.get()) stopSpeaking();
    render();
    $('#speakBtn')?.focus();
  });
  $('#micBtn')?.addEventListener('click', toggleMic);
}

async function toggleMic() {
  const btn = $('#micBtn');
  if (listening()) { stopListening(); return; }
  stopSpeaking();
  btn.setAttribute('aria-pressed', 'true');
  btn.classList.add('live');
  const input = $('#chatInput');
  input.placeholder = t('voice.listening', 'Listening…');
  try {
    const text = await listen({ onText: (txt) => { if ($('#chatInput')) $('#chatInput').value = txt; } });
    if (text) ask(text, { spoken: true });
  } catch (err) {
    log.push({ who: 'bot', text: err.message });
    render();
  } finally {
    const b = $('#micBtn');
    if (b) { b.setAttribute('aria-pressed', 'false'); b.classList.remove('live'); }
    if ($('#chatInput')) $('#chatInput').placeholder = t('asst.ph', 'Ask about eligibility, documents, deadlines');
  }
}

async function ask(q, { spoken = false } = {}) {
  q = (q || '').trim();
  if (!q || !state.profileId) return;
  log.push({ who: 'user', text: q });
  log.push({ who: 'bot', text: '', typing: true });
  render();
  try {
    const res = await api('/api/agent/assistant', { method: 'POST', json: { profile_id: state.profileId, question: q } });
    log[log.length - 1] = { who: 'bot', text: res.answer, intent: res.intent };
    if (speakOn.get() || spoken) speak(res.answer);
  } catch (err) {
    log[log.length - 1] = { who: 'bot', text: t('asst.error', 'Could not get an answer: {msg}', { msg: err.message }) };
  }
  render();
  $('#chatInput')?.focus();
}

export function openAssistant() {
  lastFocus = document.activeElement;
  render();
  $('#drawer').classList.add('open');
  $('#scrim').hidden = false;
  document.querySelectorAll('[data-assistant]').forEach((b) => b.setAttribute('aria-expanded', 'true'));
  document.body.style.overflow = 'hidden';
  setTimeout(() => ($('#chatInput:not([disabled])') || $('#drawerClose')).focus(), 50);
}

export function closeAssistant() {
  stopListening();
  stopSpeaking();
  $('#drawer').classList.remove('open');
  $('#scrim').hidden = true;
  document.querySelectorAll('[data-assistant]').forEach((b) => b.setAttribute('aria-expanded', 'false'));
  document.body.style.overflow = '';
  lastFocus?.focus?.();
}

export const assistantOpen = () => $('#drawer').classList.contains('open');

export function initAssistant() {
  $('#scrim').addEventListener('click', closeAssistant);
  document.addEventListener('keydown', (e) => {
    if (!assistantOpen()) return;
    if (e.key === 'Escape') { e.preventDefault(); closeAssistant(); }
    if (e.key === 'Tab') {   // keep focus inside the drawer while it is open
      const f = [...$('#drawer').querySelectorAll('button:not([disabled]), input:not([disabled])')];
      if (!f.length) return;
      if (e.shiftKey && document.activeElement === f[0]) { e.preventDefault(); f.at(-1).focus(); }
      else if (!e.shiftKey && document.activeElement === f.at(-1)) { e.preventDefault(); f[0].focus(); }
    }
  });
}
