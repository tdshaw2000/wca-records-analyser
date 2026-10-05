#!/bin/bash
# Installed by the one-time setup in docs/runbook.md at
# $HOME/apps/wca-records-analyser/deploy-launcher.sh -- a sibling of the git checkout
# (.../repo), never inside it. It's the forced command GitHub Actions' deploy key always
# runs (see the "command=" authorized_keys entry in docs/runbook.md); its job is to
# git-update that checkout, then hand off to deploy/run_deploy.sh from the now-current
# checkout. A script that resets the hard way the very checkout it is itself currently
# being read from can be corrupted mid-run, so this file deliberately lives somewhere
# that reset can never touch, updates the checkout, and only then execs the fresh
# run_deploy.sh.
set -euo pipefail

CHECKOUT_DIR="$HOME/apps/wca-records-analyser/repo"
INSTALL_DIR="/srv/wca-records-analyser"

cd "$CHECKOUT_DIR"
git fetch --depth 1 origin main
git reset --hard origin/main

exec deploy/run_deploy.sh "$INSTALL_DIR"
