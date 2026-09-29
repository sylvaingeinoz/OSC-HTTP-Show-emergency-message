#!/bin/bash
# Mise à jour du logiciel installé, sans toucher au système ni aux réglages.
set -euo pipefail
if [ "$(id -u)" -eq 0 ]; then echo 'Utilisez le compte de l’installation, sans sudo.' >&2; exit 1; fi
if [ ! -f "$HOME/.config/systemd/user/stop-show.service" ] || [ ! -d "$HOME/.local/share/stop-show/app" ]; then
  echo 'Installation STOP SHOW introuvable pour ce compte. Utilisez le compte de l’installation initiale.' >&2; exit 1
fi
exec 9>"${XDG_RUNTIME_DIR:-/tmp}/stop-show-install-$(id -u).lock"
flock -n 9 || { echo 'Une installation ou mise à jour est déjà en cours.' >&2; exit 1; }
download_dir=$(mktemp -d)
restart_needed=0
cleanup() {
  if [ "$restart_needed" -eq 1 ]; then systemctl --user restart stop-show-session.target || true; fi
  rm -rf -- "$download_dir"
}
trap cleanup EXIT
curl --fail --location --proto '=https' --tlsv1.2 \
  'https://github.com/sylvaingeinoz/OSC-HTTP-Show-emergency-message/archive/refs/heads/main.tar.gz' \
  --output "$download_dir/source.tar.gz"
mkdir "$download_dir/source"
tar -xzf "$download_dir/source.tar.gz" -C "$download_dir/source" --strip-components=1
# Vérifier les sources avant d’interrompre l’affichage.
python3 "$download_dir/source/pi/update_app.py" --check
restart_needed=1
systemctl --user stop stop-show-session.target
python3 "$download_dir/source/pi/update_app.py" --home "$HOME"
systemctl --user restart stop-show-session.target
restart_needed=0
printf 'Mise à jour terminée. Réglages et démarrage automatique conservés. Rechargez la régie web.\n'
