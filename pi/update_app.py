#!/usr/bin/env python3
"""Mise à jour sauvegardée du code uniquement ; aucun fichier système modifié."""
import argparse
import ast
from datetime import datetime, timezone
from pathlib import Path
import shutil
import tempfile

SOURCE = Path(__file__).resolve().parents[1]


def check_source(source):
    for name in ('server.py', 'static/admin.html', 'static/admin.js', 'static/display.html',
                 'static/display.js', 'static/style.css', 'pi/install.sh'):
        if not (source / name).is_file():
            raise ValueError('Source incomplète : ' + name)
    for path in source.rglob('*.py'):
        ast.parse(path.read_text(), filename=str(path))


def update(home, source=SOURCE):
    check_source(source)
    base = Path(home) / '.local/share/stop-show'
    app = base / 'app'
    if not app.is_dir():
        raise ValueError('Installation existante introuvable.')
    stage = Path(tempfile.mkdtemp(prefix='.update-', dir=base))
    backup = base / ('app-before-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    moved = False
    try:
        shutil.copy2(source / 'server.py', stage / 'server.py')
        for name in ('static', 'pi'):
            shutil.copytree(source / name, stage / name, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        app.rename(backup)
        moved = True
        stage.rename(app)
    except BaseException:
        if moved and not app.exists():
            backup.rename(app)
        raise
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return backup


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--home', type=Path, default=Path.home())
    args = parser.parse_args()
    if args.check:
        check_source(SOURCE)
    else:
        print('Version précédente sauvegardée :', update(args.home))
