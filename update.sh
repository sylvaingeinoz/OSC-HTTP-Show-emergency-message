#!/bin/bash
# Première mise à jour vers OTA, ou récupération manuelle du logiciel installé.
set -euo pipefail
if [ "$(id -u)" -eq 0 ]; then echo 'Utilisez le compte de l’installation, sans sudo.' >&2; exit 1; fi
if [ ! -f "$HOME/.config/systemd/user/stop-show.service" ] || [ ! -d "$HOME/.local/share/stop-show/app" ]; then
  echo 'Installation STOP SHOW introuvable pour ce compte.' >&2; exit 1
fi
exec 9>"$HOME/.stop-show-install.lock"
flock -n 9 || { echo 'Une installation ou mise à jour est déjà en cours.' >&2; exit 1; }
download_dir=$(mktemp -d)
trap 'rm -rf -- "$download_dir"' EXIT
revision=$(curl --fail --location --proto '=https' --tlsv1.2 --max-time 30 \
  'https://api.github.com/repos/sylvaingeinoz/OSC-HTTP-Show-emergency-message/commits/main' \
  | python3 -c 'import json,re,sys; s=json.load(sys.stdin)["sha"]; assert re.fullmatch("[0-9a-f]{40}",s); print(s)')
curl --fail --location --proto '=https' --tlsv1.2 --max-time 120 \
  "https://codeload.github.com/sylvaingeinoz/OSC-HTTP-Show-emergency-message/tar.gz/$revision" \
  --output "$download_dir/source.tar.gz"
mkdir "$download_dir/source"
tar -xzf "$download_dir/source.tar.gz" -C "$download_dir/source" --strip-components=1
python3 "$download_dir/source/pi/update_app.py" --check
# Le worker reprend le verrou, vérifie l’archive et contrôle la version relancée.
exec 9>&-
python3 "$download_dir/source/pi/ota_worker.py" --revision "$revision"
printf 'Mise à jour terminée. Rechargez la régie web.\n'
