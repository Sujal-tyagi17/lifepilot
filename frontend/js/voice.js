/* Voice in and out with the browser's Web Speech API, in Hindi or English.
   Note: in Chrome and Edge, speech recognition sends the audio to the browser
   maker's servers. Reading answers aloud runs on the device. */
import { getLang, langInfo } from './i18n.js';
import { store } from './util.js';

const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;

export const canListen = () => !!Recognition && window.isSecureContext !== false;
export const canSpeak = () => 'speechSynthesis' in window && typeof SpeechSynthesisUtterance === 'function';

/** Why voice input cannot work here, in words a user can act on (null when it can). */
export function whyNoVoice() {
  if (window.isSecureContext === false) return 'Voice input needs a secure page. Open LifePilot at http://localhost:8000 (not a network address).';
  if (!Recognition) return 'Voice input works in Google Chrome or Microsoft Edge. This browser does not support it.';
  if (/Brave/i.test(navigator.userAgent) || navigator.brave) return 'Brave blocks the speech service. Use Chrome or Edge for voice input.';
  return null;
}
export const voiceLang = () => langInfo().speech;

let current = null;

/** Listen once. Calls onText(partial, final) while you speak; resolves with the final text. */
export function listen({ onText = () => {}, lang = voiceLang() } = {}) {
  if (!canListen()) return Promise.reject(new Error('Voice input is not supported in this browser'));
  stopListening();
  return new Promise((resolve, reject) => {
    const rec = new Recognition();
    rec.lang = lang;
    rec.interimResults = true;
    rec.maxAlternatives = 1;
    rec.continuous = false;
    let finalText = '';
    let failed = false;
    let done = false;   // some browsers fire onend twice
    rec.onresult = (e) => {
      let interim = '';
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i];
        if (r.isFinal) finalText += r[0].transcript; else interim += r[0].transcript;
      }
      onText((finalText + interim).trim(), false);
    };
    rec.onerror = (e) => {
      current = null;
      if (e.error === 'aborted') return;   // we stopped it ourselves
      const msg = {
        'not-allowed': 'Microphone permission was refused. Click the lock icon next to the address, allow the microphone, and try again.',
        'service-not-allowed': 'The browser\'s speech service is blocked. Use Chrome or Edge, and check that it is allowed in site settings.',
        'no-speech': 'Did not hear anything. Speak right after pressing the microphone.',
        'audio-capture': 'No microphone was found. Plug one in or check your sound settings.',
        'network': 'Voice input needs an internet connection: the browser sends the audio to its speech service.',
        'language-not-supported': 'This browser cannot recognise this language. Try English or Hindi.',
      }[e.error] || `Voice input stopped (${e.error}).`;
      failed = true;
      reject(new Error(msg));
    };
    rec.onend = () => { if (current === rec) current = null; if (failed || done) return; done = true; onText(finalText.trim(), true); resolve(finalText.trim()); };
    current = rec;
    try { rec.start(); } catch (err) { current = null; reject(new Error(`Voice input could not start (${err.message})`)); }
  });
}

export function stopListening() {
  try { current?.stop(); } catch { /* already stopped */ }
  current = null;
}

export const listening = () => !!current;

/* Reading answers aloud */
export const speakOn = {
  get: () => store.get('lp_speak', false) === true,
  set: (v) => store.set('lp_speak', !!v),
};

function pickVoice(lang) {
  const voices = window.speechSynthesis.getVoices();
  return voices.find((v) => v.lang === lang) || voices.find((v) => v.lang?.replace('_', '-').startsWith(lang.slice(0, 2))) || null;
}

/* Voices load in the background; wait for them once (at most a second). */
let voicesReady = null;
function waitForVoices() {
  if (!canSpeak()) return Promise.resolve();
  if (window.speechSynthesis.getVoices().length) return Promise.resolve();
  return (voicesReady ||= new Promise((resolve) => {
    window.speechSynthesis.addEventListener('voiceschanged', () => resolve(), { once: true });
    setTimeout(resolve, 1000);
  }));
}

/** Call from a click: some browsers only allow speech that starts from a user action. */
export function unlockSpeech() {
  if (!canSpeak()) return;
  try {
    const u = new SpeechSynthesisUtterance(' ');
    u.volume = 0;
    window.speechSynthesis.speak(u);
  } catch { /* nothing to unlock */ }
  waitForVoices();
}

/** Chrome stops reading long text after about 15 seconds, so speak in short pieces. */
function chunks(text, max = 180) {
  const parts = text.match(/[^.!?।\n]+[.!?।]?/g) || [text];
  const out = [];
  for (let p of parts) {
    p = p.trim();
    while (p.length > max) {
      const cut = p.lastIndexOf(' ', max);
      out.push(p.slice(0, cut > 40 ? cut : max)); p = p.slice(cut > 40 ? cut : max).trim();
    }
    if (p) out.push(p);
  }
  return out;
}

/** Strip Markdown and links so the speech sounds natural. */
export function plain(text) {
  return String(text || '')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/https?:\/\/\S+/g, '')
    .replace(/[*_#`>]/g, '')
    .replace(/^\s*[-•]\s+/gm, '')
    .replace(/₹\s?/g, getLang() === 'en' ? 'rupees ' : '₹')
    .replace(/\s+/g, ' ')
    .trim();
}

/* Pick a voice from the script the text is written in, so a Hindi answer is
   read with a Hindi voice even when the app is in English. */
const SCRIPTS = [[/[\u0980-\u09FF]/, 'bn-IN'], [/[\u0B80-\u0BFF]/, 'ta-IN'], [/[\u0C00-\u0C7F]/, 'te-IN']];
function scriptLang(text) {
  for (const [re, l] of SCRIPTS) if (re.test(text)) return l;
  if (/[\u0900-\u097F]/.test(text)) return getLang() === 'mr' ? 'mr-IN' : 'hi-IN';
  return voiceLang();
}

export async function speak(text, lang) {
  if (!canSpeak()) return false;
  const synth = window.speechSynthesis;
  synth.cancel();
  await waitForVoices();
  // Hindi text is read with a Hindi voice even when the app is in English
  const l = lang || scriptLang(text);
  const v = pickVoice(l);
  // No voice for this language on this computer: reading it with an English voice would be gibberish
  if (!v && synth.getVoices().length && !l.startsWith('en')) return false;
  const pieces = chunks(plain(text).slice(0, 1500));
  // Chrome can drop an utterance queued in the same tick as cancel()
  setTimeout(() => {
    for (const piece of pieces) {
      const u = new SpeechSynthesisUtterance(piece);
      u.lang = l;
      if (v) u.voice = v;
      u.rate = 1;
      synth.speak(u);
    }
    if (synth.paused) synth.resume();
  }, 80);
  return true;
}

/** The language a reply would be read in (from its script). */
export const replyVoiceLang = (text) => scriptLang(text);

export function stopSpeaking() {
  if (canSpeak()) window.speechSynthesis.cancel();
}
