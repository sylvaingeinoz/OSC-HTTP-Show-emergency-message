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

let updateBusy = false, updateRequested = false;
function showUpdate(s) {
  $('update-versions').textContent = 'Version installée : ' + s.installed + (s.revision ? ' · ' + s.revision.slice(0, 7) : '') + (s.available ? ' — disponible : ' + s.available.version + ' · ' + s.available.revision.slice(0, 7) : '');
  $('update-status').textContent = s.message;
  if (!s.supported) $('update-status').textContent += ' Installation depuis cette page disponible sur le Pi uniquement.';
  $('check-update').disabled = s.busy || updateBusy;
  $('install-update').disabled = !s.supported || !s.available || s.busy || updateBusy;
  if (updateRequested && ['success', 'error'].includes(s.job.state) && !s.busy) { updateRequested = false; loadSettings().catch(() => {}); document.querySelector('iframe').src = '/display'; }
}
async function updateAction(name) {
  updateBusy = true; if (name === 'install') updateRequested = true; $('check-update').disabled = $('install-update').disabled = true;
  $('update-status').textContent = name === 'check' ? 'Recherche en cours…' : 'Lancement de l’installation…';
  try { const s = await api('updates/' + name, {}); if (name === 'install') updateRequested = true; updateBusy = false; showUpdate(s); if (name === 'check') $('update-status').textContent = s.message; }
  catch (e) { updateBusy = false; $('update-status').textContent = e.message; $('check-update').disabled = false; }
}
$('check-update').onclick = () => updateAction('check');
$('install-update').onclick = () => updateAction('install');
async function updateStatus() {
  if (!updateBusy) {
    try { const s = await api('updates'); showUpdate(s); }
    catch (_) { if (updateRequested) $('update-status').textContent = 'Application en cours de redémarrage… Reconnexion automatique.'; }
  }
  setTimeout(updateStatus, 2000);
}
updateStatus();

const remoteCommands = [
 ['Message / prompteur', 'Affiche du texte multiligne (8 000 caractères maximum).', {mode:'text',text:'LÉA · MICRO 2\nCôté cour'}, '/show/text', 'Une chaîne (s) : LÉA · MICRO 2'],
 ['Reprise', 'Raccourci de message ; remplace la consigne précédente.', {mode:'text',text:'REPRISE'}, '/show/text', 'Une chaîne (s) : REPRISE'],
 ['STOP SHOW', 'Affiche STOP SHOW en rouge clignotant.', {mode:'stop'}, '/show/stop', 'Aucun argument'],
 ['STOP personnalisé', 'Même clignotement, avec votre texte.', {mode:'stop',text:'STOP SHOW\nRestez en place'}, '/show/stop', 'Une chaîne (s) : votre texte'],
 ['Noir immédiat', 'Efface la consigne. Le signal HDMI reste actif.', {mode:'black'}, '/show/black', 'Aucun argument'],
 ['Heure', 'Affiche l’heure du Pi dans le fuseau choisi.', {mode:'clock'}, '/show/clock', 'Aucun argument'],
 ['Minuterie', 'Démarre un décompte en secondes (0 à 604 800), arrêté à zéro.', {mode:'timer',seconds:300}, '/show/timer', 'Un entier (i) ou flottant (f) : 300'],
 ['Compte à rebours', 'Décompte vers une date future avec décalage UTC obligatoire.', {mode:'countdown',target:'2027-01-01T00:00:00+01:00'}, '/show/countdown', 'Une chaîne (s) : 2027-01-01T00:00:00+01:00'],
 ['Mire', 'Affiche TV INFO CAST, le cadre, les repères et les adresses réseau.', {mode:'test'}, '/show/test', 'Aucun argument'],
 ['Prolonger', 'Réarme le délai au noir sans redémarrer le compteur ; ne réactive pas une consigne éteinte.', {mode:'keepalive'}, '/show/keepalive', 'Aucun argument']
];
const remoteEndpoints = [
 ['GET','/api/state','Consigne et état d’affichage. remaining = délai au noir (null si désactivé), cue.remaining = temps du compteur.',''],
 ['GET','/api/health','État du service, version installée et commit.',''],
 ['GET','/api/network','Adresses IPv4, hostname.local, ports et adresse d’écoute.',''],
 ['GET','/api/settings','Lire les réglages, dont le réglage HDMI sauvegardé.',''],
 ['POST','/api/settings','Modifier les réglages (objet partiel accepté ; HDMI se règle par essai/confirmation).',JSON.stringify({off_time:0,indicator:false,font:'sans',size:120,timezone:'Europe/Zurich',blink_ms:800})],
 ['GET','/api/diagnostics','Compteurs OSC reçus/rejetés et dernière erreur HDMI.',''],
 ['GET','/api/hdmi','Détecter les sorties HDMI et les modes annoncés par la TV.',''],
 ['POST','/api/hdmi/test','Essayer pendant 20 secondes. Copier le nom de sortie et le mode exact détectés.',JSON.stringify({output:'HDMI-A-1',mode:'1920x1080@60.000000Hz',transform:'180'})],
 ['POST','/api/hdmi/confirm','Confirmer l’essai dans les 20 secondes ; sans confirmation, retour au mode précédent.','{}'],
 ['GET','/api/updates','Lire la progression locale des mises à jour, sans contacter GitHub.',''],
 ['POST','/api/updates/check','Rechercher une mise à jour GitHub, sans l’installer.','{}'],
 ['POST','/api/updates/install','Installer la proposition trouvée et relancer l’application. Interrompt l’affichage ; utiliser hors représentation.','{}']
];
let networkInfo = null;
function docNode(tag, text, parent) { const el = document.createElement(tag); el.textContent = text; parent.append(el); return el; }
function docTable(parent, headings, rows) {
  const wrap = docNode('div','',parent); wrap.className = 'doc-table-wrap';
  const table = docNode('table','',wrap), head = docNode('tr','',docNode('thead','',table));
  headings.forEach(h => docNode('th',h,head));
  const body = docNode('tbody','',table);
  rows.forEach(row => { const tr = docNode('tr','',body); row.forEach(value => { const td = docNode('td','',tr); docNode('code',value,td); }); });
}
function renderRemoteDoc() {
  const root = $('remote-doc-content'); root.replaceChildren();
  const n = networkInfo;
  const host = location.hostname, httpPort = n?.http_port || location.port || '80', oscPort = n?.osc_port ?? 'indisponible';
  const base = location.origin;
  docNode('p', `HTTP : TCP ${httpPort} · OSC : UDP ${oscPort}. Hôte utilisé ici : ${host}.`, root);
  docNode('p', n ? `IPv4 du Pi : ${n.ipv4.join(' · ') || 'aucune détectée'} · mDNS : ${n.mdns}. Le nom .local fonctionne si mDNS est actif et accessible sur votre réseau ; sinon utilisez l’IP.` : 'Adresses indisponibles : vérifiez la connexion au service.',root);
  docNode('p','Aucun compte, clé ou en-tête Authorization. Utilisez le réseau de régie. Dans Companion : Generic HTTP Requests ou Generic OSC (UDP).',root);
  docNode('h3','Commandes d’affichage · HTTP',root);
  docNode('p',`Méthode POST · URL ${base}/api/command · Content-Type: application/json. Le corps JSON détermine la commande.`,root);
  docTable(root,['Commande','Rôle','Corps JSON'],remoteCommands.map(c => [c[0],c[1],JSON.stringify(c[2])]));
  docNode('h3','Exemple HTTP',root);
  docNode('pre',`curl --fail-with-body -X POST '${base}/api/command' \\\n  -H 'Content-Type: application/json' \\\n  --data '{"mode":"stop"}'`,root);
  docNode('p','Le texte reste du texte brut. Dans JSON, un retour à la ligne s’écrit \\n et un guillemet s’écrit \\". Une réponse 200 confirme la réception par le service, pas l’image réelle sur la TV. Erreurs : 400 commande invalide, 413 corps trop grand, 415 type de contenu incorrect, 503 HDMI indisponible.',root);
  docNode('h3','Commandes d’affichage · OSC',root);
  docNode('p',`Destination : ${host} · port UDP ${oscPort}. Les chemins ci-dessous reçoivent uniquement les arguments indiqués : aucune clé en premier argument.`,root);
  docTable(root,['Commande','Chemin OSC','Arguments'],remoteCommands.map(c => [c[0],c[3],c[4]]));
  docNode('p','Types OSC : s = chaîne UTF-8, i = entier 32 bits, f = flottant 32 bits. Messages OSC simples uniquement ; aucun bundle ni timetag. Maximum 16 384 octets. Pas d’accusé de réception OSC ni de feedback. HTTP est préférable si vous voulez confirmer la réception logicielle.',root);
  docNode('h3','Délai au noir et compteurs',root);
  docNode('p','Chaque nouvelle consigne remplace la précédente et réarme le délai, STOP SHOW compris. Retour au noir = 0 désactive ce délai pour tous les modes. Sinon, keepalive prolonge une consigne encore active. Ne répétez pas timer pour maintenir l’image : cela redémarre la minuterie. La perte du service fait passer l’afficheur au noir même avec un délai à 0.',root);
  docNode('p','Le compte à rebours utilise l’heure du Pi : vérifiez sa synchronisation et choisissez une date future. L’exemple du 1er janvier 2027 doit être adapté après cette date. STOP SHOW n’a pas de priorité persistante ; la dernière commande reçue gagne.',root);
  docNode('h3','Autres opérations HTTP',root);
  docTable(root,['Méthode','Chemin','Rôle','Corps JSON'],remoteEndpoints);
  docNode('p','Réglages : off_time 0–86400 s ; indicator true/false ; font sans/serif/mono ; size 24–400 ; timezone nom IANA (Europe/Zurich) ; blink_ms 500–3000. Passer à 0 désactive immédiatement le délai d’une consigne visible ; repasser à un délai positif le réactive. Entre deux délais positifs, le changement vaut pour la prochaine commande ou prolongation.',root);
  docNode('p','Transformations HDMI : normal, 90, 180, 270, flipped, flipped-90, flipped-180, flipped-270. Le paramètre mode doit correspondre exactement à une valeur retournée par GET /api/hdmi.',root);
}
async function loadNetwork() {
  try {
    networkInfo = await api('network');
    const n = networkInfo; $('footer-ports').textContent = `HTTP / TCP : ${n.http_port} · OSC / UDP : ${n.osc_port ?? 'indisponible'} · Réseau de régie`; $('network-addresses').replaceChildren();
    docNode('span', 'IP : ' + (n.ipv4.join(' · ') || 'aucune IPv4 réseau détectée') + ' — mDNS : ', $('network-addresses'));
    const link = docNode('a', n.mdns, $('network-addresses')); link.href = `http://${n.mdns}:${n.http_port}/`; link.target = '_blank'; link.rel = 'noopener';
    $('network-ports').textContent = `HTTP / TCP : ${n.http_port} · OSC / UDP : ${n.osc_port ?? 'indisponible'} · .local nécessite mDNS sur le réseau.` + (n.listen_address === '127.0.0.1' ? ' Service limité à cet ordinateur (127.0.0.1).' : '');
  } catch (_) { $('network-addresses').textContent = 'Adresses réseau indisponibles. Vérifiez la liaison au Pi.'; }
  setTimeout(loadNetwork,30000);
}
$('open-remote-doc').onclick = () => { renderRemoteDoc(); $('remote-doc').showModal(); };
$('close-remote-doc').onclick = () => $('remote-doc').close();
loadNetwork();
