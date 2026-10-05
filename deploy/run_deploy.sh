#!/bin/bash
# Run by deploy-launcher.sh once the git checkout is current. Installs this checkout's
# deploy/ files into INSTALL_DIR -- the same files the one-time setup in docs/runbook.md
# used to extract from the image by hand (its old step 4) -- without touching .env or
# bad-images, which exist only on the server and are never part of this checkout, then
# runs the pull deploy once. Still safe to also leave on a timer (pull_deploy.py is
# idempotent either way), but docs/runbook.md no longer does.
set -euo pipefail

INSTALL_DIR="${1:?Usage: run_deploy.sh <install-dir>}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

install -d -m 755 "$INSTALL_DIR"
cp -a "$SCRIPT_DIR"/. "$INSTALL_DIR"/

exec python3 "$INSTALL_DIR/pull_deploy.py"
