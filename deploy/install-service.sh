#!/usr/bin/env bash
# Builds the dashboard and installs the engine as a systemd service that starts on boot.
# Run as the user who owns the project: bash deploy/install-service.sh
set -euo pipefail

SERVICE=parking-disposition
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$PROJECT_DIR/.venv/bin/python"

die() {
    echo "ERROR: $1" >&2
    exit 1
}

[ "$(id -u)" -ne 0 ] || die "Run this as the user who owns the project, not root. It asks for sudo when it needs to."
command -v systemctl >/dev/null || die "systemctl not found. This script needs a Linux system running systemd."
case "$PROJECT_DIR" in
    *[[:space:]]*) die "The project path has a space in it, which the service file can't use: $PROJECT_DIR" ;;
esac

cd "$PROJECT_DIR"

"$PYTHON" -c "import flask_socketio" 2>/dev/null \
    || die "$PYTHON can't load the app's packages. Fix or recreate .venv, then run this again."

if command -v npm >/dev/null; then
    [ -d node_modules ] || npm ci
    npm run build
elif [ -f dist/index.html ]; then
    echo "WARNING: npm not found, so the existing dist folder will be used and may be out of date."
else
    die "npm not found and there is no dist folder, so there's no dashboard to serve. Install Node.js and run this again."
fi

UNIT_FILE="$(mktemp)"
trap 'rm -f "$UNIT_FILE"' EXIT
sed -e "s|__USER__|$(id -un)|g" -e "s|__PROJECT_DIR__|$PROJECT_DIR|g" deploy/$SERVICE.service > "$UNIT_FILE"

sudo install -m 644 "$UNIT_FILE" "/etc/systemd/system/$SERVICE.service"
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE"
sudo systemctl restart "$SERVICE"

# Give a crash at startup time to show up in the status below
sleep 5
systemctl --no-pager --lines=15 status "$SERVICE" || true

APP_PORT="$("$PYTHON" -c "from scripts.config import get_servers; print(get_servers()['app_port'])" | tail -n 1)"
echo
echo "Dashboard: http://$(hostname):$APP_PORT"
echo "Logs:      journalctl -u $SERVICE -f"
