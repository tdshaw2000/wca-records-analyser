"""deploy/compose.yaml: the web app and the nightly build, sharing the scramble stack's VM."""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "deploy" / "compose.yaml"
IMAGE = "ghcr.io/tdshaw2000/wca-records-analyser"
DATA_DIR = "/srv/wca-data"
DB_PATH = "/srv/wca-data/wca.sqlite"
ALIAS = "wca-records-analyser"


def _compose():
    return yaml.safe_load(COMPOSE.read_text())


def _service(name):
    return _compose()["services"][name]


def _data_mount(service):
    mounts = [m for m in service["volumes"] if isinstance(m, dict) and m["target"] == DATA_DIR]
    assert len(mounts) == 1, "expected one long-form bind mount of the data directory"
    assert mounts[0]["type"] == "bind" and mounts[0]["source"] == DATA_DIR
    return mounts[0]


def _bytes(size):
    number, unit = re.fullmatch(r"(\d+)([kmg])", str(size).lower()).groups()
    return int(number) * 1024 ** "kmg".index(unit) * 1024


def test_the_project_has_its_own_name_so_it_never_touches_the_scramble_stack():
    assert _compose()["name"] == "wca-records-analyser"


def test_both_services_run_the_image_the_pull_deploy_pins():
    for name in ("web", "build"):
        assert _service(name)["image"] == f"${{WCA_IMAGE:-{IMAGE}:main}}"


def test_the_web_app_reads_the_database_through_a_read_only_mount():
    web = _service("web")
    assert _data_mount(web)["read_only"] is True
    assert web["environment"]["WCA_DATA_DB_PATH"] == DB_PATH


def test_the_web_app_publishes_no_port_on_the_host():
    web = _service("web")
    assert "ports" not in web
    assert web.get("network_mode") is None


def test_the_web_app_is_reached_by_the_scramble_caddy_over_its_network():
    web = _service("web")
    assert web["networks"] == {"edge": {"aliases": [ALIAS]}}
    edge = _compose()["networks"]["edge"]
    assert edge["external"] is True
    assert edge["name"] == "${EDGE_NETWORK:-scramble-challenge_default}"


def test_the_web_app_restarts_and_has_a_read_only_root_filesystem():
    web = _service("web")
    assert web["restart"] == "unless-stopped"
    assert web["read_only"] is True
    assert "/tmp" in web["tmpfs"]


def test_the_build_writes_the_data_directory_and_pings_the_monitor():
    build = _service("build")
    assert _data_mount(build).get("read_only", False) is False
    assert build["environment"]["WCA_DATA_DB_PATH"] == DB_PATH
    assert build["environment"]["WCA_DATA_PING_URL"] == "${WCA_DATA_PING_URL:-}"
    assert "WCA_DATA_ACCEPT_SENTINEL_CHANGE" not in build["environment"]


def test_the_build_runs_only_when_asked_and_never_restarts():
    build = _service("build")
    assert build["profiles"] == ["build"]
    assert build.get("restart", "no") == "no"
    assert build["healthcheck"] == {"disable": True}


def test_the_build_runs_at_the_lowest_cpu_and_io_priority_inside_the_container():
    # systemd's Nice= and IOSchedulingClass= would only reach the docker client, not the
    # build, which runs under containerd; so the container's own command lowers its priority.
    assert _service("build")["command"] == [
        "nice", "-n", "19", "ionice", "-c", "3", "python", "-m", "wca_data.build",
    ]


def test_the_build_cant_take_the_whole_vm_from_the_scramble_app():
    build = _service("build")
    assert float(build["cpus"]) <= 1
    assert build["cpu_shares"] < 1024
    assert _bytes(build["mem_limit"]) <= _bytes("2g")


def test_the_build_is_not_on_the_caddy_network():
    assert "edge" not in _service("build").get("networks", [])


def test_every_service_has_a_memory_limit_and_rotated_logs():
    for name, service in _compose()["services"].items():
        assert "mem_limit" in service, name
        logging = service["logging"]
        assert logging["driver"] == "json-file", name
        assert "max-size" in logging["options"] and "max-file" in logging["options"], name
