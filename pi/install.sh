#!/bin/bash
# Installation ou mise à jour sur un Pi dédié, depuis le compte créé dans Imager.
set -euo pipefail
if [ "$(id -u)" -eq 0 ]; then
  echo 'Lancez bash pi/install.sh sans sudo ; le script demandera les droits nécessaires.' >&2
  exit 1
fi
if [ ! -f /etc/rpi-issue ] || [ ! -f /boot/firmware/cmdline.txt ] || ! command -v systemctl >/dev/null; then
  echo 'Raspberry Pi OS récent 64 bits avec bureau et systemd requis.' >&2
  exit 1
fi
if [ ! -f /etc/lightdm/lightdm.conf ]; then
  echo 'Cette installation nécessite Raspberry Pi OS avec bureau (LightDM), pas Lite.' >&2
  exit 1
fi
case "$HOME" in *' '*|*'%'*|*'"'*) echo 'Chemin utilisateur non pris en charge.' >&2; exit 1;; esac
source_dir="$(cd "$(dirname "$0")/.." && pwd)"
install_dir="$HOME/.local/share/stop-show/app"
current_user=$(id -un)
# Un seul installateur à la fois, y compris lors d'une mise à jour.
exec 9>"${XDG_RUNTIME_DIR:-/tmp}/stop-show-install-$(id -u).lock"
flock -n 9 || { echo 'Une installation est déjà en cours.' >&2; exit 1; }
sudo -v
sudo apt-get update
sudo apt-get install -y python3 chromium labwc swaybg wlr-randr fonts-dejavu-core
mkdir -p "$install_dir/static" "$install_dir/pi/labwc" "$HOME/.config/systemd/user" "$HOME/.local/bin"
# Garder la clé et les réglages hors du code mis à jour.
cp "$source_dir/server.py" "$install_dir/server.py"
cp "$source_dir/static/"* "$install_dir/static/"
cp "$source_dir/pi/"*.sh "$source_dir/pi/configure_pi.py" "$install_dir/pi/"
cp "$source_dir/pi/labwc/"* "$install_dir/pi/labwc/"
cp "$source_dir/pi/kiosk.sh" "$HOME/.local/bin/stop-show-kiosk"
cp "$source_dir/pi/session.sh" "$HOME/.local/bin/stop-show-session"
chmod 755 "$HOME/.local/bin/stop-show-kiosk" "$HOME/.local/bin/stop-show-session"
python3 - "$install_dir" <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from server import App
App(Path.home() / '.local/share/stop-show/data')
PY
cat > "$HOME/.config/systemd/user/stop-show-session.target" <<'EOF'
[Unit]
Description=Stop Show - session de scene
Wants=stop-show.service stop-show-kiosk.service
EOF
cat > "$HOME/.config/systemd/user/stop-show.service" <<'EOF'
[Unit]
Description=Stop Show - service HTTP et OSC
PartOf=stop-show-session.target
StartLimitIntervalSec=0
[Service]
Type=simple
ExecStart=/usr/bin/python3 %h/.local/share/stop-show/app/server.py --host 0.0.0.0 --data %h/.local/share/stop-show/data
Restart=always
RestartSec=2
UMask=0077
NoNewPrivileges=yes
EOF
cat > "$HOME/.config/systemd/user/stop-show-kiosk.service" <<'EOF'
[Unit]
Description=Stop Show - ecran de scene Chromium
PartOf=stop-show-session.target
After=stop-show.service
StartLimitIntervalSec=0
[Service]
ExecStart=%h/.local/bin/stop-show-kiosk
Restart=always
RestartSec=2
KillMode=control-group
UMask=0077
NoNewPrivileges=yes
EOF
# Retirer uniquement l'ancien ajout v1.0 ; sauvegarder le fichier utilisateur.
python3 - <<'PY'
from pathlib import Path
p = Path.home() / '.config/labwc/autostart'
if p.exists():
    text = p.read_text()
    block = '# STOP-SHOW-AUTOSTART\n"$HOME/.local/bin/stop-show-session" &'
    if block in text:
        backup = p.with_name('autostart.before-stop-show-1.1')
        if not backup.exists(): backup.write_text(text)
        p.write_text(text.replace(block, ''))
PY
# Sauvegardes créées une seule fois ; aucune coupure de session pendant l'installation.
sudo python3 "$source_dir/pi/configure_pi.py" --user "$current_user"
systemctl --user daemon-reload
sudo systemctl daemon-reload
sudo systemctl enable lightdm.service
sudo systemctl set-default graphical.target
printf '\nInstallation terminée. Après sudo reboot, STOP SHOW se lancera automatiquement.\n'
printf 'Régie : http://%s.local:8080 (ou IP du Pi).\n' "$(hostname)"
printf 'Clé : cat ~/.local/share/stop-show/data/token\n'
printf 'Restauration du bureau : bash ~/.local/share/stop-show/app/pi/restore-desktop.sh\n'
