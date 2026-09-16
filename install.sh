#!/bin/bash
# Point d'entrée unique : depuis le dépôt ou après téléchargement de ce fichier seul.
set -euo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$script_dir/pi/install.sh" ]; then
  exec bash "$script_dir/pi/install.sh" "$@"
fi
if [ ! -f /etc/rpi-issue ]; then
  echo 'Ce script doit être exécuté sur le Raspberry Pi, depuis SSH.' >&2
  exit 1
fi
command -v curl >/dev/null || { echo 'curl requis : sudo apt-get install curl' >&2; exit 1; }
download_dir=$(mktemp -d)
trap 'rm -rf -- "$download_dir"' EXIT
curl --fail --location --proto '=https' --tlsv1.2 \
  'https://github.com/sylvaingeinoz/OSC-HTTP-Show-emergency-message/archive/refs/heads/main.tar.gz' \
  --output "$download_dir/source.tar.gz"
mkdir "$download_dir/source"
tar -xzf "$download_dir/source.tar.gz" -C "$download_dir/source" --strip-components=1
bash "$download_dir/source/pi/install.sh" "$@"
