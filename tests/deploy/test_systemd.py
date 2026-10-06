"""deploy/systemd: the nightly build timer and the admin-digest timer.

The pull-deploy timer is gone (superseded by the SSH-triggered deploy, docs/runbook.md);
pull_deploy.py itself is unchanged and still runs, now from deploy/run_deploy.sh."""

import configparser
import shlex
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UNITS = ROOT / "deploy" / "systemd"
# deploy/ is installed at this path on the VM (docs/runbook.md).
INSTALL_DIR = "/srv/wca-records-analyser"


def _unit(name):
    parser = configparser.ConfigParser(strict=False, interpolation=None)
    parser.optionxform = str
    parser.read_string((UNITS / name).read_text())
    return parser


def _exec_start(name):
    return shlex.split(_unit(name)["Service"]["ExecStart"])


def test_the_build_service_runs_the_build_service_of_this_compose_project():
    service = _unit("wca-data-build.service")["Service"]
    assert service["Type"] == "oneshot"
    assert service["WorkingDirectory"] == INSTALL_DIR
    assert _exec_start("wca-data-build.service") == ["/usr/bin/docker", "compose", "run", "--rm", "build"]
    assert "TimeoutStartSec" in service


def test_the_deploy_timer_is_gone():
    assert not (UNITS / "wca-deploy.service").exists()
    assert not (UNITS / "wca-deploy.timer").exists()


def test_the_services_start_after_docker_and_the_network():
    for name in (
        "wca-data-build.service",
        "wca-admin-digest.service",
    ):
        unit = _unit(name)["Unit"]
        assert "docker.service" in unit["Requires"].split(), name
        assert {"docker.service", "network-online.target"} <= set(unit["After"].split()), name
        assert "network-online.target" in unit["Wants"].split(), name


def test_the_build_runs_nightly_outside_busy_hours_and_catches_up_after_downtime():
    timer = _unit("wca-data-build.timer")
    assert timer["Timer"]["OnCalendar"] == "*-*-* 03:30:00 UTC"
    assert timer["Timer"]["Persistent"] == "true"
    assert "RandomizedDelaySec" in timer["Timer"]
    assert timer["Install"]["WantedBy"] == "timers.target"


def test_the_admin_digest_service_runs_the_installed_collector_script():
    service = _unit("wca-admin-digest.service")["Service"]
    assert service["Type"] == "oneshot"
    assert service["WorkingDirectory"] == INSTALL_DIR
    command = _exec_start("wca-admin-digest.service")
    assert command == ["/usr/bin/python3", f"{INSTALL_DIR}/collect_admin_log.py"]
    # Bounds a hung `docker compose logs`, like the build (2h) and deploy (15min) services.
    assert "TimeoutStartSec" in service


def test_the_admin_digest_runs_every_five_minutes():
    timer = _unit("wca-admin-digest.timer")["Timer"]
    assert timer["OnBootSec"] == "2min"
    assert timer["OnUnitInactiveSec"] == "5min"
    assert _unit("wca-admin-digest.timer")["Install"]["WantedBy"] == "timers.target"
