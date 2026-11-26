"""Mises à jour depuis une source fixe, déclenchées explicitement par la régie."""
import json
import os
from pathlib import Path
import re
import subprocess
import threading
import time
from urllib.request import Request, urlopen

REPO = 'sylvaingeinoz/OSC-HTTP-Show-emergency-message'
ROOT = Path(__file__).resolve().parent

def read_json(path, default):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return default

def get_json(url):
    with urlopen(Request(url, headers={'User-Agent': 'StopShow-Updater'}), timeout=10) as response:
        return json.loads(response.read(1048576))

def version(root=ROOT):
    return read_json(root / 'version.json', {'version': 'inconnue'})['version']

def latest():
    commit = get_json(f'https://api.github.com/repos/{REPO}/commits/main')['sha']
    if not re.fullmatch('[0-9a-f]{40}', commit):
        raise ValueError('Révision GitHub invalide.')
    release = get_json(f'https://raw.githubusercontent.com/{REPO}/{commit}/version.json')
    if not re.fullmatch(r'\d+\.\d+\.\d+', release.get('version', '')):
        raise ValueError('Version GitHub invalide.')
    return {'revision': commit, 'version': release['version']}

class Updates:
    def __init__(self, root=ROOT, home=None):
        self.root, self.home = root, home or Path.home()
        self.base = self.home / '.local/share/stop-show'
        self.lock = threading.Lock()
        self.available = None
        self.checked_at = 0
        self.message = 'Recherchez les mises à jour.'

    def supported(self):
        return (self.root.resolve() == (self.base / 'app').resolve() and
                (self.home / '.config/systemd/user/stop-show.service').is_file())

    def status(self):
        job = read_json(self.base / 'update-status.json', {}) if self.supported() else {}
        busy = False
        if self.supported():
            # Le verrou appartient au processus, jamais à un simple fichier périmé.
            import fcntl
            with open(lock_path(), 'a') as handle:
                try:
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    busy = True
        if job.get('state') == 'installing' and not busy and time.time() - job.get('time', 0) > 15:
            job = {'state': 'error', 'time': time.time(), 'message': 'Mise à jour interrompue. Relancez une recherche ou utilisez SSH.'}
        return dict(installed=version(self.root), revision=read_json(self.root / 'revision.json', {}).get('revision'),
                    available=self.available, supported=self.supported(), busy=busy,
                    message=job.get('message', self.message) if job.get('time', 0) > self.checked_at or busy else self.message, job=job)

    def check(self):
        with self.lock:
            self.available = None
            self.checked_at = time.time()
            try:
                candidate = latest()
                current = read_json(self.root / 'revision.json', {}).get('revision')
                if candidate['revision'] != current:
                    # Installation initiale sans identifiant de commit : comparer la version.
                    if current or candidate['version'] != version(self.root):
                        self.available = candidate
                self.message = 'Mise à jour disponible.' if self.available else 'Vous disposez de la dernière version.'
            except Exception as exc:
                self.message = 'Recherche impossible : vérifiez Internet et réessayez. ' + str(exc)[:160]
                raise ValueError(self.message) from exc
            return self.status()

    def install(self):
        with self.lock:
            if not self.supported():
                raise ValueError('Installation OTA disponible uniquement sur le Pi installé.')
            if not self.available:
                raise ValueError('Recherchez d’abord une mise à jour disponible.')
            if self.status()['busy']:
                raise ValueError('Une installation est déjà en cours.')
            from pi.ota_worker import status
            status(self.base, 'installing', 'Installation lancée…')
            # Unité indépendante de stop-show.service : elle survit à son arrêt.
            try:
                subprocess.run(['systemd-run', '--user', '--collect', '--unit=stop-show-update',
                                '--property=Type=exec', '/usr/bin/python3',
                                str(self.root / 'pi/ota_worker.py'), '--revision', self.available['revision']],
                               check=True, capture_output=True, timeout=10)
            except (OSError, subprocess.SubprocessError) as exc:
                status(self.base, 'error', 'Lancement impossible ; réessayez après vérification du journal.')
                raise ValueError('Impossible de lancer la mise à jour ; une autre peut être en cours. Consultez le journal stop-show-update.') from exc
            self.available = None
            self.message = 'Installation lancée. Attendez la reconnexion automatique.'
            return self.status()

def lock_path():
    return str(Path.home() / '.stop-show-install.lock')
