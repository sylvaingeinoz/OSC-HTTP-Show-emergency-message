#!/bin/bash
set -euo pipefail
script_dir="$(cd "$(dirname "$0")" && pwd)"
# Restaurer les fichiers système sauvegardés avant la première installation 1.1.
sudo python3 "$script_dir/configure_pi.py" --restore
sudo systemctl daemon-reload
printf 'Configuration antérieure restaurée. Redémarrez avec sudo reboot.\n'
printf 'Les messages, clés et réglages applicatifs n’ont pas été supprimés.\n'
