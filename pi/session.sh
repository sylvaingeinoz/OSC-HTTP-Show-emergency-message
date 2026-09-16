#!/bin/bash
set -euo pipefail
# Importer le socket réel de labwc et le thème de curseur de cette session.
vars=(WAYLAND_DISPLAY XDG_RUNTIME_DIR XDG_SESSION_TYPE XCURSOR_THEME XCURSOR_PATH XCURSOR_SIZE)
if [ -n "${DISPLAY:-}" ]; then vars+=(DISPLAY); fi
systemctl --user import-environment "${vars[@]}"
systemctl --user restart stop-show-session.target
