#!/usr/bin/env python3
"""Configuration système réversible. --root permet les tests hors Raspberry Pi."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import struct

HERE = Path(__file__).resolve().parent


def quiet_cmdline(text):
    if len(text.strip().splitlines()) != 1:
        raise ValueError('cmdline.txt doit contenir exactement une ligne non vide.')
    options = ['quiet', 'loglevel=3', 'logo.nologo', 'vt.global_cursor_default=0',
               'systemd.show_status=false', 'rd.systemd.show_status=false', 'plymouth.enable=0']
    keys = {o.split('=')[0] for o in options} | {'splash'}
    kept = []
    for token in text.split():
        if token.split('=')[0] in keys:
            continue
        # Garder la console série ; éloigner seulement la console HDMI initiale.
        if token == 'console=tty1':
            token = 'console=tty3'
        kept.append(token)
    return ' '.join(kept + options) + '\n'


def firmware_config(text):
    begin, end = '# BEGIN STOP-SHOW', '# END STOP-SHOW'
    text = re.sub(r'(?m)^# BEGIN STOP-SHOW\n.*?^# END STOP-SHOW\n?', '', text, flags=re.S)
    return text.rstrip() + f'\n\n{begin}\n[all]\ndisable_splash=1\n{end}\n'


def lightdm_config(text, user):
    values = {'autologin-user': user, 'autologin-user-timeout': '0',
              'autologin-session': 'stop-show', 'user-session': 'stop-show'}
    # Appliquer à tous les sièges existants pour éviter un override de Seat:*.
    lines, out, in_seat = text.splitlines(), [], False
    has_seat = False
    for line in lines + ['[STOP_SHOW_EOF]']:
        if re.match(r'^\s*\[', line):
            if in_seat:
                out.extend(f'{k}={v}' for k, v in values.items())
            in_seat = bool(re.match(r'^\s*\[Seat:', line))
            has_seat |= in_seat
        if line == '[STOP_SHOW_EOF]':
            break
        if in_seat and re.match(r'^\s*#?\s*(' + '|'.join(values) + r')\s*=', line):
            continue
        out.append(line)
    if not has_seat:
        out.extend(['', '[Seat:*]'] + [f'{k}={v}' for k, v in values.items()])
    return '\n'.join(out).rstrip() + '\n'


def transparent_cursor():
    # Xcursor : entête + table des matières + image ARGB transparente 1 × 1.
    return (struct.pack('<4I', 0x72756358, 16, 0x10000, 1)
            + struct.pack('<3I', 0xfffd0002, 24, 28)
            + struct.pack('<9I', 36, 0xfffd0002, 24, 1, 1, 1, 0, 0, 0)
            + b'\0' * 4)


class Installer:
    def __init__(self, root):
        self.root = Path(root)
        self.backup = self.root / 'var/lib/stop-show-install'
        self.manifest_path = self.backup / 'manifest.json'
        self.manifest = json.loads(self.manifest_path.read_text()) if self.manifest_path.exists() else {}

    def write(self, relative, content, mode=0o644):
        dest = self.root / relative
        if relative not in self.manifest:
            if dest.is_symlink():
                raise ValueError(f'Configuration liée non prise en charge : {dest}')
            old = self.backup / 'files' / relative
            if dest.exists():
                old.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dest, old)
                self.manifest[relative] = dest.stat().st_mode & 0o777
            else:
                self.manifest[relative] = None
            self.backup.mkdir(parents=True, exist_ok=True)
            self.manifest_path.write_text(json.dumps(self.manifest, indent=2))
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content.encode() if isinstance(content, str) else content)
        dest.chmod(mode)

    def apply(self, user):
        if not re.fullmatch(r'[a-z_][a-z0-9_-]*', user):
            raise ValueError('Nom de compte Linux invalide.')
        boot = self.root / 'boot/firmware'
        cmdline = quiet_cmdline((boot / 'cmdline.txt').read_text())
        firmware = firmware_config((boot / 'config.txt').read_text())
        config_path = self.root / 'etc/lightdm/lightdm.conf'
        lightdm = lightdm_config(config_path.read_text() if config_path.exists() else '', user)
        # Calcul et validation avant toute écriture.
        self.write('boot/firmware/cmdline.txt', cmdline)
        self.write('boot/firmware/config.txt', firmware)
        self.write('etc/lightdm/lightdm.conf', lightdm)
        self.write('usr/local/bin/stop-show-desktop', (HERE / 'desktop.sh').read_text(), 0o755)
        self.write('usr/share/wayland-sessions/stop-show.desktop',
                   '[Desktop Entry]\nName=Stop Show\nComment=Afficheur de scène\n'
                   'Exec=/usr/local/bin/stop-show-desktop\nType=Application\nDesktopNames=StopShow\n')
        for name in ('rc.xml', 'autostart', 'shutdown'):
            self.write('etc/stop-show/labwc/' + name, (HERE / 'labwc' / name).read_text(),
                       0o644 if name.endswith('.xml') else 0o755)
        self.write('etc/stop-show/labwc/menu.xml', '<?xml version="1.0"?><openbox_menu/>\n')
        self.write('etc/stop-show/labwc/environment', 'XCURSOR_THEME=stop-show-blank\nXCURSOR_SIZE=24\n')
        self.write('etc/stop-show/icons/stop-show-blank/index.theme',
                   '[Icon Theme]\nName=Stop Show Blank\nComment=Curseur transparent\n')
        for cursor in ('left_ptr', 'default', 'arrow', 'top_left_arrow', 'watch', 'wait',
                       'left_ptr_watch', 'progress', 'pointer', 'hand2', 'text', 'xterm',
                       'crosshair', 'move', 'not-allowed', 'size_all'):
            self.write('etc/stop-show/icons/stop-show-blank/cursors/' + cursor, transparent_cursor())
        # Pas d'invite de connexion sur le VT visible entre noyau et LightDM.
        self.write('etc/systemd/system/getty@tty1.service.d/stop-show.conf',
                   '[Service]\nExecStart=\nExecStart=/usr/bin/sleep infinity\n'
                   'StandardInput=null\nStandardOutput=null\n')

    def restore(self):
        for relative, mode in self.manifest.items():
            dest = self.root / relative
            if mode is None:
                dest.unlink(missing_ok=True)
            else:
                shutil.copy2(self.backup / 'files' / relative, dest)
        # Les sauvegardes sont conservées et restent utilisables après restauration.


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', default='/')
    p.add_argument('--user')
    p.add_argument('--restore', action='store_true')
    args = p.parse_args()
    if args.root == '/' and os.geteuid() != 0:
        p.error('Exécuter avec sudo sur le Pi.')
    installer = Installer(args.root)
    if args.restore:
        installer.restore()
    elif args.user:
        installer.apply(args.user)
    else:
        p.error('--user requis')


if __name__ == '__main__':
    main()
