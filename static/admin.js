'use strict';
const $ = id => document.getElementById(id);
let outputs = [], confirmUntil = 0;
function notice(message, error = false) { $('notice').textContent = message; $('notice').className = error ? 'error' : 'success'; }
async function api(path, body) {
  const r = await fetch('/api/' + path, {method: body === undefined ? 'GET' : 'POST', headers: {'Content-Type': 'application/json'}, body: body === undefined ? undefined : JSON.stringify(body), signal: AbortSignal.timeout(25000)});
  const result = await r.json();
  if (!r.ok) throw new Error(result.error || 'Erreur de communication');
  return result;
}
async function action(fn) { try { await fn(); } catch (e) { notice(e.message, true); } }
async function command(data) { await api('command', data); notice(data.mode === 'black' ? 'Écran au noir.' : 'Consigne transmise.'); }
async function loadSettings() {
  const s = await api('settings');
  for (const [name, value] of Object.entries(s)) if ($(name)) { if (name === 'indicator') $(name).checked = value; else $(name).value = value; }
}
$('send').onclick = () => action(() => command({mode: 'text', text: $('message').value}));
$('resume').onclick = () => action(() => command({mode: 'text', text: 'REPRISE'}));
for (const mode of ['stop', 'black', 'clock', 'test', 'keepalive']) $(mode).onclick = () => action(() => command({mode}));
$('timer').onclick = () => action(() => command({mode: 'timer', seconds: Number($('seconds').value)}));
$('countdown').onclick = () => action(() => command({mode: 'countdown', target: $('target').value}));
$('settings').onsubmit = event => { event.preventDefault(); action(async () => {
  await api('settings', {off_time: Number($('off_time').value), size: Number($('size').value), font: $('font').value, blink_ms: Number($('blink_ms').value), timezone: $('timezone').value.trim(), indicator: $('indicator').checked});
  notice('Réglages enregistrés. 0 désactive le retour au noir, y compris pour la consigne en cours.');
}); };
function modes() {
  const out = outputs.find(o => o.name === $('output').value);
  $('mode').replaceChildren();
  if (!out) return;
  for (const m of out.modes) { const option = new Option(m.id.replace('@', ' · ') + (m.current ? ' · actuel' : ''), m.id); option.selected = m.current; $('mode').add(option); }
  $('transform').value = out.transform;
}
$('output').onchange = modes;
$('refresh-hdmi').onclick = () => action(async () => {
  $('test-hdmi').disabled = true;
  const result = await api('hdmi'); outputs = result.outputs.filter(o => o.enabled);
  $('output').replaceChildren();
  for (const o of outputs) $('output').add(new Option(o.name, o.name));
  $('output').disabled = $('mode').disabled = !outputs.length;
  modes(); $('test-hdmi').disabled = !outputs.length;
  $('hdmi-status').textContent = result.error || (outputs.length ? 'Modes détectés. Vérifiez tout changement directement sur le téléviseur.' : 'Aucune sortie HDMI active détectée.');
});
$('test-hdmi').onclick = () => action(async () => {
  const result = await api('hdmi/test', {output: $('output').value, mode: $('mode').value, transform: $('transform').value});
  confirmUntil = performance.now() + 19000; $('confirm-hdmi').disabled = false; notice(result.message);
});
$('confirm-hdmi').onclick = () => action(async () => { const r = await api('hdmi/confirm', {}); confirmUntil = 0; $('confirm-hdmi').disabled = true; notice(r.message); });
const labels = {black: 'Écran noir', text: 'Message', stop: 'STOP SHOW', clock: 'Heure', timer: 'Minuterie', countdown: 'Compte à rebours', test: 'Mire'};
async function status() {
  try {
    const r = await fetch('/api/state', {signal: AbortSignal.timeout(1500)}); if (!r.ok) throw new Error(); const s = await r.json();
    $('connection').textContent = '● Service en ligne'; $('connection').className = 'badge';
    $('mode-label').textContent = labels[s.cue.mode]; $('off-label').textContent = s.cue.mode === 'black' ? 'Aucune consigne' : s.remaining === null ? 'Retour au noir désactivé' : 'Noir dans ' + Math.ceil(s.remaining) + ' s';
  } catch (_) { $('connection').textContent = '● Liaison perdue'; $('connection').className = 'badge offline'; $('off-label').textContent = 'État indisponible'; }
  if (confirmUntil && performance.now() >= confirmUntil) { confirmUntil = 0; $('confirm-hdmi').disabled = true; notice('Délai de confirmation terminé. Détectez les modes pour vérifier le retour arrière.'); }
  setTimeout(status, 500);
}
action(loadSettings);
status();
