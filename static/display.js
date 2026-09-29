'use strict';
const stage = document.querySelector('#stage'), content = document.querySelector('#content');
const pattern = document.querySelector('#pattern'), pilot = document.querySelector('#pilot');
const stateURL = location.protocol === 'file:' ? 'http://127.0.0.1:8080/api/state' : '/api/state';
let state = null, received = 0, expires = 0, requestDuration = 0, fitKey = '';
const fonts = {sans: 'Arial, Helvetica, sans-serif', serif: 'Georgia, serif', mono: 'monospace'};
function duration(seconds) {
  const n = Math.max(0, Math.ceil(seconds));
  return [Math.floor(n / 3600), Math.floor(n / 60) % 60, n % 60].map(x => String(x).padStart(2, '0')).join(':');
}
function fit(text, config) {
  const key = [text, config.size, config.font, innerWidth, innerHeight].join('|');
  if (key === fitKey) return;
  fitKey = key;
  content.textContent = text;
  content.style.fontFamily = fonts[config.font];
  let low = 1, high = config.size * innerHeight / 1080;
  // Recherche de la plus grande taille qui montre tout le message sans défilement.
  for (let i = 0; i < 12; i++) {
    const mid = (low + high) / 2;
    content.style.fontSize = mid + 'px';
    if (content.scrollHeight > stage.clientHeight * .88 || content.scrollWidth > content.clientWidth + 1) high = mid;
    else low = mid;
  }
  content.style.fontSize = low + 'px';
}
function render() {
  const now = performance.now();
  const online = state && now - received < 2000;
  const config = state?.config;
  const mode = online && now < expires ? state.cue.mode : 'black';
  if (stage.className !== mode) stage.className = mode;
  pilot.hidden = !config?.indicator;
  pilot.style.background = online ? '#50c98b' : '#db9b38';
  pattern.hidden = mode !== 'test';
  content.hidden = mode === 'black' || mode === 'test';
  if (!config) return;
  stage.style.setProperty('--blink', config.blink_ms + 'ms');
  let text = state.cue.text || '';
  const elapsed = (now - received + requestDuration) / 1000;
  if (mode === 'clock') text = new Intl.DateTimeFormat('fr-CH', {timeZone: config.timezone, hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23'}).format(new Date((state.server_time + elapsed) * 1000));
  if (mode === 'timer' || mode === 'countdown') text = duration(state.cue.remaining - elapsed);
  if (!content.hidden) fit(text, config);
  if (mode === 'test') document.querySelector('#dimensions').textContent = `${innerWidth} × ${innerHeight}`;
}
async function poll() {
  const started = performance.now();
  try {
    const r = await fetch(stateURL, {cache: 'no-store', signal: AbortSignal.timeout(1500)});
    if (!r.ok) throw new Error('Connexion');
    const next = await r.json();
    received = performance.now();
    requestDuration = received - started;
    state = next;
    expires = state.remaining === null ? Infinity : received + Math.max(0, state.remaining * 1000 - requestDuration);
  } catch (_) { /* Le rendu coupe automatiquement au noir en cas de perte de liaison. */ }
  render();
  setTimeout(poll, 200);
}
setInterval(render, 100);
poll();
