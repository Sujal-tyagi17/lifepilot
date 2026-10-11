/* Voice in and out with the browser's Web Speech API, in Hindi or English.
   Note: in Chrome and Edge, speech recognition sends the audio to the browser
   maker's servers. Reading answers aloud runs on the device. */
import { getLang } from './i18n.js';
import { store } from './util.js';

const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;

export const canListen = () => !!Recognition && window.isSecureContext !== false;
export const canSpeak = () => 'speechSynthesis' in window && typeof SpeechSynthesisUtterance === 'function';
export const voiceLang = () => (getLang() === 'hi' ? 'hi-IN' : 'en-IN');

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
      const msg = e.error === 'not-allowed' || e.error === 'service-not-allowed' ? 'Microphone permission was refused'
        : e.error === 'no-speech' ? 'Did not hear anything. Try again'
          : e.error === 'network' ? 'Voice input needs an internet connection' : `Voice input stopped (${e.error})`;
      reject(new Error(msg));
    };
    rec.onend = () => { current = null; onText(finalText.trim(), true); resolve(finalText.trim()); };
    current = rec;
    rec.start();
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
  return voices.find((v) => v.lang === lang) || voices.find((v) => v.lang?.startsWith(lang.slice(0, 2))) || null;
}

/** Strip Markdown and links so the speech sounds natural. */
export function plain(text) {
  return String(text || '')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/https?:\/\/\S+/g, '')
    .replace(/[*_#`>]/g, '')
    .replace(/^\s*[-•]\s+/gm, '')
    .replace(/₹\s?/g, getLang() === 'hi' ? '₹' : 'rupees ')
    .replace(/\s+/g, ' ')
    .trim();
}

export function speak(text, lang) {
  if (!canSpeak()) return;
  window.speechSynthesis.cancel();
  // Hindi text is read with a Hindi voice even when the app is in English
  const l = lang || (/[ऀ-ॿ]/.test(text) ? 'hi-IN' : voiceLang());
  const u = new SpeechSynthesisUtterance(plain(text).slice(0, 1200));
  u.lang = l;
  const v = pickVoice(l);
  if (v) u.voice = v;
  u.rate = 1;
  window.speechSynthesis.speak(u);
}

export function stopSpeaking() {
  if (canSpeak()) window.speechSynthesis.cancel();
}
