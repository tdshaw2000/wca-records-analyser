"""deploy/deploy-launcher.sh and deploy/run_deploy.sh: the SSH-triggered deploy.

Deployment files can't be unit tested for real: the first live deploy is the proof. These
tests pin down what the scripts must do (see tests/test_deploy_config.py in the scramble
repo this pattern is copied from)."""

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "deploy" / "deploy-launcher.sh"
RUN_DEPLOY = ROOT / "deploy" / "run_deploy.sh"
CHECKOUT_DIR = "$HOME/apps/wca-records-analyser/repo"
INSTALL_DIR = "/srv/wca-records-analyser"


def text(path):
    return path.read_text()


def test_the_launcher_and_run_deploy_are_valid_and_executable():
    for script in (LAUNCHER, RUN_DEPLOY):
        assert os.access(script, os.X_OK)
        subprocess.run(["bash", "-n", str(script)], check=True)


def test_the_launcher_updates_the_checkout_before_handing_off():
    # git reset --hard rewrites every tracked file, including whichever one is the
    # running forced command. A file outside the checkout (even if it's a sibling
    # inside the same app folder) is never touched by that reset, so the launcher does
    # the git update from outside the checkout, then execs run_deploy.sh fresh, only
    # once the checkout is current.
    script = text(LAUNCHER)

    assert CHECKOUT_DIR in script
    assert "git fetch" in script
    fetch = script.index("git fetch")
    reset = script.index("git reset --hard")
    handoff = script.index("exec deploy/run_deploy.sh")
    assert fetch < reset < handoff


def test_the_launcher_passes_the_install_dir_run_deploy_writes_into():
    script = text(LAUNCHER)
    assert f'INSTALL_DIR="{INSTALL_DIR}"' in script
    assert 'exec deploy/run_deploy.sh "$INSTALL_DIR"' in script


def _code_lines(script):
    """Script lines with full-line comments dropped, so a rationale comment that happens
    to name something (.env, pull_deploy.py, ...) can't be mistaken for the code itself."""
    return "\n".join(line for line in script.splitlines() if not line.strip().startswith("#"))


def test_run_deploy_installs_this_checkouts_deploy_files_without_excluding_anything():
    # .env and bad-images live only on the server and are never part of the checkout,
    # so a plain recursive copy can't overwrite them -- no --exclude flag is needed.
    code = _code_lines(text(RUN_DEPLOY))
    assert "cp -a" in code
    assert "--exclude" not in code


def test_run_deploy_runs_pull_deploy_from_the_install_dir_last():
    code = _code_lines(text(RUN_DEPLOY))
    copy = code.index("cp -a")
    run = code.index("pull_deploy.py")
    assert copy < run
    assert "exec python3" in code


def test_run_deploy_takes_the_install_dir_as_its_one_argument():
    script = text(RUN_DEPLOY)
    assert 'INSTALL_DIR="${1:?' in script
