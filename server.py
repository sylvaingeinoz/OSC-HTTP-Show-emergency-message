#!/usr/bin/env python3
"""Afficheur de scène — Python 3.9+, bibliothèque standard uniquement."""
import argparse
import copy
import datetime as dt
import json
import logging
import math
import os
from pathlib import Path
import re
import socketserver
import struct
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ROOT = Path(__file__).resolve().parent
DEFAULT = dict(off_time=15, indicator=False, font='sans', size=120,
               timezone='Europe/Zurich', blink_ms=800, hdmi=None)
TRANSFORMS = ('normal', '90', '180', '270', 'flipped', 'flipped-90', 'flipped-180', 'flipped-270')


def number(value, low, high, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'{name} : nombre attendu entre {low} et {high}.')
    return value


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    with tmp.open('w', encoding='utf8') as f:
        os.chmod(tmp, 0o600)
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def settings(current, patch):
    if not isinstance(patch, dict) or set(patch) - (set(DEFAULT) - {'hdmi'}):
        raise ValueError('Réglage inconnu ou format invalide.')
    c = {**current, **patch}
    number(c['off_time'], 0, 86400, 'Délai au noir')
    number(c['size'], 24, 400, 'Taille')
    number(c['blink_ms'], 500, 3000, 'Période de clignotement')
    if type(c['indicator']) is not bool or c['font'] not in ('sans', 'serif', 'mono'):
        raise ValueError('Police ou témoin invalide.')
    try:
        ZoneInfo(c['timezone'])
    except (TypeError, ValueError, ZoneInfoNotFoundError):
        raise ValueError('Fuseau horaire IANA invalide.')
    return c


class DisplayHardware:
    """Commandes sans shell, modes annoncés par le compositeur Wayland."""
    def run(self, *args):
        try:
            p = subprocess.run(['wlr-randr', *args], capture_output=True, text=True,
                               timeout=8, env={**os.environ, 'LC_ALL': 'C'})
        except (OSError, subprocess.TimeoutExpired) as e:
            raise ValueError('HDMI indisponible : session Wayland et wlr-randr requis.') from e
        if p.returncode:
            raise ValueError('Réglage HDMI refusé : ' + p.stderr.strip()[:300])
        return p.stdout

    def outputs(self):
        result, current = [], None
        for line in self.run().splitlines():
            if line and not line[0].isspace():
                current = dict(name=line.split()[0], modes=[], transform='normal', enabled=False)
                result.append(current)
            elif current:
                m = re.match(r'\s+(\d+)x(\d+) px, ([\d.]+) Hz(.*)', line)
                if m:
                    w, h, hz, flags = m.groups()
                    mode = f'{w}x{h}@{hz}Hz'
                    current['modes'].append(dict(id=mode, current='current' in flags, preferred='preferred' in flags))
                if 'Transform:' in line:
                    current['transform'] = line.split(':', 1)[1].strip()
                if 'Enabled:' in line:
                    current['enabled'] = line.split(':', 1)[1].strip() == 'yes'
        return [o for o in result if o['name'].startswith('HDMI')]

    def validate(self, data):
        if not isinstance(data, dict) or set(data) != {'output', 'mode', 'transform'} or data['transform'] not in TRANSFORMS:
            raise ValueError('Réglage HDMI invalide.')
        out = next((o for o in self.outputs() if o['name'] == data['output'] and o['enabled']), None)
        if not out or data['mode'] not in [m['id'] for m in out['modes']]:
            raise ValueError('Sortie active ou mode annoncé introuvable.')
        old = next((m['id'] for m in out['modes'] if m['current']), None)
        if not old:
            raise ValueError('Mode actuel inconnu : retour arrière impossible.')
        return dict(output=out['name'], mode=old, transform=out['transform'])

    def apply(self, data):
        self.run('--output', data['output'], '--mode', data['mode'], '--transform', data['transform'])


class App:
    def __init__(self, directory, hardware=None, mono=time.monotonic, wall=time.time):
        self.directory = Path(directory)
        self.lock = threading.RLock()
        self.mono, self.wall = mono, wall
        self.hardware = hardware or DisplayHardware()
        self.config_path = self.directory / 'settings.json'
        self.config = copy.deepcopy(DEFAULT)
        if self.config_path.exists():
            loaded = json.loads(self.config_path.read_text())
            self.config = settings(self.config, {k: v for k, v in loaded.items() if k != 'hdmi'})
            self.config['hdmi'] = loaded.get('hdmi')
        self.directory.mkdir(parents=True, exist_ok=True)
        self.cue = dict(mode='black', text='')
        self.deadline = 0
        self.revision = 0
        self.pending = None
        self.hdmi_error = None
        self.osc_received = 0
        self.osc_rejected = 0

    def configure(self, data):
        with self.lock:
            new = settings(self.config, data)
            save_json(self.config_path, new)
            if self.cue['mode'] != 'black' and (self.deadline is None or self.mono() < self.deadline):
                if new['off_time'] == 0:
                    self.deadline = None
                elif self.config['off_time'] == 0:
                    self.deadline = self.mono() + new['off_time']
            self.config = new
            # Hors activation/désactivation du délai, les réglages ne réarment rien.
            return copy.deepcopy(new)

    def command(self, data):
        if not isinstance(data, dict):
            raise ValueError('Objet JSON attendu.')
        mode = data.get('mode')
        allowed = {'mode', 'text'} if mode in ('text', 'stop') else {'mode', 'seconds'} if mode == 'timer' else {'mode', 'target'} if mode == 'countdown' else {'mode'}
        if set(data) - allowed:
            raise ValueError('Champ inconnu pour cette commande.')
        with self.lock:
            now = self.mono()
            if mode == 'keepalive':
                if self.cue['mode'] != 'black' and (self.deadline is None or now < self.deadline):
                    self.deadline = now + self.config['off_time'] if self.config['off_time'] else None
                return self.snapshot()
            cue = dict(mode=mode, text='')
            if mode in ('text', 'stop'):
                text = data.get('text', 'STOP SHOW' if mode == 'stop' else '')
                if not isinstance(text, str) or not text.strip() or len(text) > 8000:
                    raise ValueError('Texte requis, de 1 à 8000 caractères.')
                cue['text'] = text
            elif mode == 'timer':
                seconds = number(data.get('seconds'), 0, 604800, 'Durée')
                cue['timer_end'] = now + seconds
            elif mode == 'countdown':
                value = data.get('target')
                try:
                    target = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
                    if target.tzinfo is None or target.utcoffset() is None:
                        raise ValueError()
                except (AttributeError, TypeError, ValueError):
                    raise ValueError('Cible ISO 8601 avec date et décalage requis, ex. 2027-01-01T00:00:00+01:00.')
                if target.timestamp() <= self.wall():
                    raise ValueError('La cible doit être future.')
                cue['target'] = target.timestamp()
            elif mode not in ('black', 'clock', 'test'):
                raise ValueError('Commande inconnue.')
            self.cue = cue
            self.deadline = (now + self.config['off_time'] if self.config['off_time'] else None) if mode != 'black' else 0
            self.revision += 1
            return self.snapshot()

    def snapshot(self):
        with self.lock:
            now, wall = self.mono(), self.wall()
            remaining = None if self.deadline is None else max(0, self.deadline - now)
            cue = copy.deepcopy(self.cue) if remaining is None or remaining > 0 else dict(mode='black', text='')
            if cue['mode'] == 'timer':
                cue['remaining'] = max(0, cue.pop('timer_end') - now)
            if cue['mode'] == 'countdown':
                cue['remaining'] = max(0, cue['target'] - wall)
            return dict(cue=cue, remaining=remaining, server_time=wall, revision=self.revision,
                        config={k: v for k, v in self.config.items() if k != 'hdmi'})

    def hdmi_test(self, data):
        with self.lock:
            if self.pending:
                raise ValueError('Un essai HDMI est déjà en cours.')
            old = self.hardware.validate(data)
            try:
                self.hardware.apply(data)
            except ValueError:
                self.hardware.apply(old)
                raise
            self.pending = dict(old=old, new=copy.deepcopy(data), until=self.mono() + 20)
            self.hdmi_error = None
            return {'message': 'Vérifiez le téléviseur et confirmez sous 20 secondes.'}

    def hdmi_confirm(self):
        with self.lock:
            self.tick()
            if not self.pending:
                raise ValueError('Aucun essai HDMI à confirmer.')
            new = {**self.config, 'hdmi': self.pending['new']}
            save_json(self.config_path, new)
            self.config = new
            self.pending = None
            return {'message': 'Réglage HDMI enregistré.'}

    def tick(self):
        with self.lock:
            if self.pending and self.mono() >= self.pending['until']:
                try:
                    self.hardware.apply(self.pending['old'])
                    self.hdmi_error = 'Essai non confirmé : ancien mode restauré.'
                except ValueError as e:
                    self.hdmi_error = 'Échec du retour arrière : ' + str(e)
                    logging.error(self.hdmi_error)
                self.pending = None

    def restore(self):
        if self.config['hdmi']:
            try:
                self.hardware.validate(self.config['hdmi'])
                self.hardware.apply(self.config['hdmi'])
            except ValueError as e:
                self.hdmi_error = str(e)
                logging.warning('Mode enregistré non appliqué : %s', e)


def decode_osc(packet):
    """Messages OSC 1.0 simples, types s/i/f ; bundles et types inconnus rejetés."""
    if len(packet) > 16384 or len(packet) % 4:
        raise ValueError('Paquet OSC invalide.')
    pos = 0
    def string():
        nonlocal pos
        end = packet.find(b'\0', pos)
        if end < 0:
            raise ValueError('Chaîne OSC invalide.')
        value = packet[pos:end].decode('utf8')
        nxt = (end + 4) & ~3
        if nxt > len(packet) or any(packet[end:nxt]):
            raise ValueError('Alignement OSC invalide.')
        pos = nxt
        return value
    address, tags = string(), string()
    if not address.startswith('/show/') or not tags.startswith(','):
        raise ValueError('Adresse OSC invalide.')
    args = []
    for tag in tags[1:]:
        if tag == 's':
            args.append(string())
        elif tag in ('i', 'f'):
            if pos + 4 > len(packet):
                raise ValueError('Argument OSC incomplet.')
            args.append(struct.unpack_from('>' + tag, packet, pos)[0])
            pos += 4
        else:
            raise ValueError('Type OSC non pris en charge.')
    if pos != len(packet):
        raise ValueError('Octets OSC supplémentaires.')
    return address, args


def osc_command(app, packet):
    address, args = decode_osc(packet)
    mode = address[6:]
    count = 1 if mode in ('text', 'timer', 'countdown') else 0
    if mode == 'stop' and len(args) == 1:
        count = 1
    if len(args) != count:
        raise ValueError('Nombre d’arguments OSC invalide.')
    data = {'mode': mode}
    if count == 1:
        data['seconds' if mode == 'timer' else 'target' if mode == 'countdown' else 'text'] = args[0]
    return app.command(data)


class UDPServer(socketserver.UDPServer):
    allow_reuse_address = True
    max_packet_size = 65535


class OSCHandler(socketserver.BaseRequestHandler):
    def handle(self):
        try:
            osc_command(self.server.app, self.request[0])
            self.server.app.osc_received += 1
        except (ValueError, UnicodeError, struct.error):
            self.server.app.osc_rejected += 1


class Handler(BaseHTTPRequestHandler):
    server_version = 'StopShow/1.2'
    def setup(self):
        super().setup()
        self.connection.settimeout(5)

    def log_message(self, format, *args):
        pass  # Pas de consignes ou de secrets dans les journaux HTTP.

    def reply(self, code, value, kind='application/json; charset=utf-8'):
        body = json.dumps(value, ensure_ascii=False).encode() if not isinstance(value, bytes) else value
        self.send_response(code)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        # Lecture publique uniquement : la page locale du kiosque a une origine null.
        if urlsplit(self.path).path == '/api/state' and self.command == 'GET':
            self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; frame-ancestors 'self'; object-src 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlsplit(self.path).path
        app = self.server.app
        if path == '/api/state':
            return self.reply(200, app.snapshot())
        if path == '/api/health':
            return self.reply(200, dict(ok=True, version='1.2.0'))
        if path in ('/api/settings', '/api/hdmi', '/api/diagnostics'):
            try:
                with app.lock:
                    if path == '/api/settings':
                        value = copy.deepcopy(app.config)
                    elif path == '/api/diagnostics':
                        value = dict(osc_received=app.osc_received, osc_rejected=app.osc_rejected,
                                     hdmi_error=app.hdmi_error, server_time=app.wall())
                    else:
                        value = dict(outputs=app.hardware.outputs(), pending=bool(app.pending), error=app.hdmi_error)
                return self.reply(200, value)
            except ValueError as e:
                return self.reply(503, {'error': str(e)})
        files = {'/': ('admin.html', 'text/html'), '/display': ('display.html', 'text/html'),
                 '/admin.js': ('admin.js', 'text/javascript'), '/display.js': ('display.js', 'text/javascript'),
                 '/style.css': ('style.css', 'text/css')}
        if path in files:
            name, kind = files[path]
            return self.reply(200, (ROOT / 'static' / name).read_bytes(), kind + '; charset=utf-8')
        self.reply(404, {'error': 'Page introuvable.'})

    def do_POST(self):
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 32768:
                return self.reply(413, {'error': 'Corps JSON requis, maximum 32 Ko.'})
            if self.headers.get_content_type() != 'application/json':
                return self.reply(415, {'error': 'Content-Type application/json requis.'})
            data = json.loads(self.rfile.read(size))
            app = self.server.app
            path = urlsplit(self.path).path
            if path == '/api/command':
                value = app.command(data)
            elif path == '/api/settings':
                value = app.configure(data)
            elif path == '/api/hdmi/test':
                value = app.hdmi_test(data)
            elif path == '/api/hdmi/confirm':
                value = app.hdmi_confirm()
            else:
                return self.reply(404, {'error': 'Commande introuvable.'})
            self.reply(200, value)
        except (ValueError, UnicodeError) as e:
            self.reply(400, {'error': str(e)})
        except OSError:
            logging.exception('Erreur de stockage')
            self.reply(500, {'error': 'Enregistrement impossible. Vérifiez le stockage.'})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--osc-port', type=int, default=9000)
    parser.add_argument('--data', default=str(Path.home() / '.local/share/stop-show'))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    app = App(args.data)
    app.restore()
    http = ThreadingHTTPServer((args.host, args.port), Handler)
    http.app = app
    udp = UDPServer((args.host, args.osc_port), OSCHandler)
    udp.app = app
    def maintenance():
        while True:
            app.tick()
            time.sleep(.2)
    threading.Thread(target=maintenance, daemon=True).start()
    threading.Thread(target=udp.serve_forever, daemon=True).start()
    logging.info('Prêt : HTTP %s:%s / OSC UDP %s.', args.host, args.port, args.osc_port)
    try:
        http.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        udp.shutdown()
        udp.server_close()
        http.server_close()


if __name__ == '__main__':
    main()
