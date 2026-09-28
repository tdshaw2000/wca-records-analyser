"""Pull deploy for the VM, run every five minutes by wca-deploy.service (docs/runbook.md).

Pulls the newest main image from GHCR. If its digest differs from the one pinned as WCA_IMAGE
in .env, pins it, restarts the web service and waits for its health check. An image that
doesn't turn healthy is rolled back to the previous digest and written to bad-images, so it
isn't tried again. GitHub Actions never connects to the VM; the VM only pulls a public image.

Standard library only: this runs on the host's python3, not in the image.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPOSITORY = "ghcr.io/tdshaw2000/wca-records-analyser"
IMAGE = f"{REPOSITORY}:main"
BUILD_SERVICE = "wca-data-build.service"
SOURCE_LABEL = "org.opencontainers.image.source=https://github.com/tdshaw2000/wca-records-analyser"
INSTALL_DIR = Path("/srv/wca-records-analyser")
ENV_FILE = ".env"
BAD_IMAGES_FILE = "bad-images"
KEY = "WCA_IMAGE"
WAIT_SECONDS = 120


class DeployFailed(Exception):
    """The new image wasn't deployed. The message says what is running now."""


def _read_env(folder):
    path = folder / ENV_FILE
    return path.read_text().splitlines() if path.exists() else []


def _pinned(lines):
    for line in lines:
        if line.startswith(KEY + "="):
            return line.split("=", 1)[1]
    return None


def _pin(folder, image):
    """Set WCA_IMAGE (or remove it when image is None), keeping every other line of .env."""
    path = folder / ENV_FILE
    lines = [line for line in _read_env(folder) if not line.startswith(KEY + "=")]
    if image is not None:
        lines.append(f"{KEY}={image}")
    mode = (path.stat().st_mode & 0o777) if path.exists() else 0o600
    descriptor, temporary = tempfile.mkstemp(dir=folder, prefix=".env.")
    try:
        with os.fdopen(descriptor, "w") as file:
            file.write("".join(line + "\n" for line in lines))
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def _bad_images(folder):
    path = folder / BAD_IMAGES_FILE
    return set(path.read_text().split()) if path.exists() else set()


def _remember_bad(folder, image):
    with open(folder / BAD_IMAGES_FILE, "a") as file:
        file.write(image + "\n")


def _digest(run):
    """The pulled image's digest reference in this repository, e.g. ghcr.io/...@sha256:..."""
    result = run(["docker", "image", "inspect", "--format", "{{json .RepoDigests}}", IMAGE])
    if result.returncode == 0:
        for reference in json.loads(result.stdout or "null") or []:
            if reference.startswith(REPOSITORY + "@sha256:"):
                return reference
    raise DeployFailed(f"{IMAGE} has no digest from {REPOSITORY}; nothing changed")


def _start_web(run):
    command = ["docker", "compose", "up", "-d", "--wait", "--wait-timeout", str(WAIT_SECONDS), "web"]
    return run(command).returncode == 0


def deploy(folder, run):
    """One check. Returns what happened; raises DeployFailed if the new image isn't running."""
    folder = Path(folder)
    if run(["docker", "pull", "-q", IMAGE]).returncode != 0:
        raise DeployFailed(f"docker pull {IMAGE} failed; nothing changed")
    new = _digest(run)
    live = _pinned(_read_env(folder))
    if new == live:
        return "up to date"
    if new in _bad_images(folder):
        return "skipped a known-bad image"
    _pin(folder, new)
    if _start_web(run):
        run(["docker", "image", "prune", "--force", "--filter", f"label={SOURCE_LABEL}"])
        # A new image may carry a bumped SCHEMA_VERSION; the health check doesn't read the
        # database, so rebuild straight away rather than waiting for the nightly timer.
        run(["systemctl", "start", BUILD_SERVICE])
        return "deployed"
    _remember_bad(folder, new)
    _pin(folder, live)
    if live is None:
        raise DeployFailed(f"{new} didn't turn healthy and there is nothing to roll back to")
    if not _start_web(run):
        raise DeployFailed(f"{new} didn't turn healthy, and the rollback to {live} failed too")
    raise DeployFailed(f"{new} didn't turn healthy; rolled back to {live}")


def _run_in(folder):
    def run(args):
        return subprocess.run(args, cwd=folder, stdout=subprocess.PIPE, text=True)

    return run


def main(folder=INSTALL_DIR, run=None):
    run = run or _run_in(folder)
    try:
        outcome = deploy(folder, run)
    except DeployFailed as error:
        print(f"pull deploy failed: {error}", file=sys.stderr)
        return 1
    print(f"pull deploy: {outcome}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
