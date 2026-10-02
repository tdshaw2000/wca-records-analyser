"""Filters the web container's access log down to the lines the admin page needs.

Run every five minutes by wca-admin-digest.service (docs/runbook.md). The web container has
no docker access of its own (it's read-only, uid 10001, on no privileged network), so this
runs on the host and writes a plain text file the container reads read-only
(wca_records_analyser.web, WCA_ADMIN_LOG_PATH): one access-log line per request that named a
wca_id, same as the owner's own `docker compose logs -t web | grep wca_id`.

Standard library only: this runs on the host's python3, not in the image.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT = "wca-records-analyser"
SERVICE = "web"
WCA_ID_MARKER = "wca_id="
OUTPUT_PATH = Path("/srv/wca-admin/usage.log")


class CollectFailed(Exception):
    """The log wasn't collected. The message says why."""


def collect(run, output_path=OUTPUT_PATH):
    """One run: filter the service's logs and write them to output_path. Returns the count."""
    result = run(["docker", "compose", "-p", PROJECT, "logs", "-t", SERVICE])
    if result.returncode != 0:
        raise CollectFailed(f"docker compose -p {PROJECT} logs -t {SERVICE} failed")
    lines = [line for line in result.stdout.splitlines() if WCA_ID_MARKER in line]
    _write_atomic(output_path, "".join(line + "\n" for line in lines))
    return len(lines)


def _write_atomic(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".usage.")
    try:
        with os.fdopen(descriptor, "w") as file:
            file.write(text)
        # Written as root (a systemd service); the web container reads it as its own
        # non-root user, so it needs to be world-readable, unlike pull_deploy.py's .env.
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def main():
    def run(args):
        return subprocess.run(args, stdout=subprocess.PIPE, text=True)

    try:
        count = collect(run)
    except CollectFailed as error:
        print(f"collect admin log failed: {error}", file=sys.stderr)
        return 1
    print(f"collect admin log: {count} lines")
    return 0


if __name__ == "__main__":
    sys.exit(main())
