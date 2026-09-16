#!/bin/bash
set -euo pipefail
# Un profil neuf à chaque lancement évite toute restauration après coupure.
: "${XDG_RUNTIME_DIR:?Session utilisateur Wayland requise}"
profile_dir=$(mktemp -d "$XDG_RUNTIME_DIR/stop-show-browser.XXXXXX")
child=''
cleanup() {
  trap - EXIT TERM INT
  if [ -n "$child" ]; then
    kill "$child" 2>/dev/null || true
    wait "$child" 2>/dev/null || true
  fi
  rm -rf -- "$profile_dir"
}
trap cleanup EXIT
trap 'exit 0' TERM INT
# La page est locale : si le service est arrêté, elle reste noire et réessaie.
/usr/bin/chromium --ozone-platform=wayland --kiosk --no-first-run \
  --no-default-browser-check --noerrdialogs --disable-session-crashed-bubble \
  --disable-notifications --disable-features=Translate,MediaRouter \
  --force-dark-mode --password-store=basic \
  --user-data-dir="$profile_dir" \
  "file://$HOME/.local/share/stop-show/app/static/display.html" &
child=$!
wait "$child"
