#!/usr/bin/env python3
"""Téléchargement épinglé, remplacement sauvegardé et contrôle de reprise."""
import argparse
import fcntl
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from urllib.request import Request, urlopen
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ota import REPO, latest, lock_path, version
from pi.update_app import check_source, update

def status(base, state, message):
    path = base / 'update-status.json'
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(dict(state=state, message=message, time=time.time())))
    tmp.replace(path)

def download(revision, destination):
    if not re.fullmatch('[0-9a-f]{40}', revision):
        raise ValueError('Révision invalide.')
    archive = destination / 'source.tar.gz'
    with urlopen(Request(f'https://codeload.github.com/{REPO}/tar.gz/{revision}',
                         headers={'User-Agent': 'StopShow-Updater'}), timeout=30) as response, archive.open('wb') as out:
        total = 0
        while True:
            chunk = response.read(65536)
            if not chunk: break
            total += len(chunk)
            if total > 32 * 1024 * 1024: raise ValueError('Archive trop volumineuse.')
            out.write(chunk)
    source = destination / 'source'
    source.mkdir()
    with tarfile.open(archive) as tar:
        members = tar.getmembers()
        if len(members) > 5000 or sum(m.size for m in members) > 64 * 1024 * 1024:
            raise ValueError('Archive trop volumineuse.')
        for member in members:
            parts = PurePosixPath(member.name).parts
            if not parts or member.name.startswith('/') or '..' in parts or not (member.isdir() or member.isfile()):
                raise ValueError('Archive invalide.')
            target = source.joinpath(*parts[1:])
            if member.isdir(): target.mkdir(parents=True, exist_ok=True)
            elif len(parts) > 1:
                target.parent.mkdir(parents=True, exist_ok=True)
                with tar.extractfile(member) as inp, target.open('wb') as out: shutil.copyfileobj(inp, out)
                target.chmod(member.mode & 0o755)
    check_source(source)
    subprocess.run([sys.executable, str(source / 'server.py'), '--help'],
                   check=True, capture_output=True, timeout=15,
                   env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
    (source / 'revision.json').write_text(json.dumps({'revision': revision}))
    return source

def control(action):
    subprocess.run(['systemctl', '--user', action, 'stop-show-session.target'], check=True, timeout=30,
                   stdout=subprocess.DEVNULL)

def healthy(revision):
    deadline = time.monotonic() + 35
    while time.monotonic() < deadline:
        try:
            with urlopen('http://127.0.0.1:8080/api/health', timeout=2) as response:
                if json.load(response).get('revision') == revision: return True
        except Exception: pass
        time.sleep(1)
    return False

def deploy(home, source, revision, ctl=control, health=healthy):
    base = home / '.local/share/stop-show'
    backup = None
    try:
        ctl('stop')
        backup = update(home, source)
        ctl('start')
        if not health(revision): raise RuntimeError('La nouvelle version ne répond pas correctement.')
        status(base, 'success', 'Mise à jour terminée : ' + version(base / 'app') + '. Réglages conservés.')
    except Exception as exc:
        if backup:
            ctl('stop')
            failed = base / ('app-failed-' + str(time.time_ns()))
            (base / 'app').rename(failed)
            backup.rename(base / 'app')
        ctl('start')
        status(base, 'error', 'Échec : ' + str(exc)[:180] + (' Ancienne version restaurée.' if backup else ' Code précédent conservé.'))
        raise

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--revision')
    args = parser.parse_args()
    home = Path.home()
    base = home / '.local/share/stop-show'
    if os.getuid() == 0 or not (base / 'app').is_dir():
        raise SystemExit('Utilisez le compte de l’installation, sans sudo.')
    with open(lock_path(), 'a') as lock:
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: raise SystemExit('Une installation est déjà en cours.')
        status(base, 'installing', 'Téléchargement et vérification…')
        try:
            revision = args.revision or latest()['revision']
            with tempfile.TemporaryDirectory(prefix='stop-show-update-') as tmp:
                source = download(revision, Path(tmp))
                status(base, 'installing', 'Installation et redémarrage…')
                deploy(home, source, revision)
        except Exception as exc:
            old = json.loads((base / 'update-status.json').read_text())
            if old['state'] != 'error': status(base, 'error', 'Mise à jour impossible : ' + str(exc)[:200])
            raise

if __name__ == '__main__': main()
