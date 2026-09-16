#!/bin/bash
# Session LightDM dédiée : aucun bureau, panneau ou service de notifications.
set -u
export XCURSOR_THEME=stop-show-blank
export XCURSOR_PATH=/etc/stop-show/icons:/usr/share/icons
export XCURSOR_SIZE=24
export XDG_CURRENT_DESKTOP=StopShow
export XDG_SESSION_TYPE=wayland
child=''
trap 'trap - TERM INT; if [ -n "$child" ]; then kill "$child" 2>/dev/null || true; wait "$child" 2>/dev/null || true; fi; exit 0' TERM INT
while true; do
  /usr/bin/labwc -C /etc/stop-show/labwc &
  child=$!
  wait "$child" || true
  child=''
  # Garder la session ouverte pour éviter le retour au sélecteur de connexion.
  sleep 2
done
