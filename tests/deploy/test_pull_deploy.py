"""deploy/pull_deploy.py: the VM pulls new main images, keeps healthy ones, rolls back others."""

import functools
import importlib.util
import json
import os
import stat
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "deploy" / "pull_deploy.py"
REPO = "ghcr.io/tdshaw2000/wca-records-analyser"
OLD = f"{REPO}@sha256:" + "a" * 64
NEW = f"{REPO}@sha256:" + "b" * 64


@functools.cache
def _load():
    spec = importlib.util.spec_from_file_location("pull_deploy", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _LoadedOnUse:
    """The script as a module, loaded on first use so each test fails alone while it is missing."""

    def __getattr__(self, name):
        return getattr(_load(), name)


pull_deploy = _LoadedOnUse()


class Result:
    def __init__(self, returncode=0, stdout=""):
        self.returncode = returncode
        self.stdout = stdout


class FakeDocker:
    """Answers the docker commands the script runs, recording each with the .env it saw."""

    def __init__(self, folder, digests=(NEW,), healthy=True, pull_fails=False):
        self.folder = folder
        self.digests = list(digests)
        self.healthy = healthy
        self.pull_fails = pull_fails
        self.commands = []
        self.env_at_up = []

    def __call__(self, args):
        self.commands.append(args)
        if args[:2] == ["docker", "pull"]:
            return Result(1 if self.pull_fails else 0)
        if args[:3] == ["docker", "image", "inspect"]:
            return Result(0, json.dumps(self.digests) + "\n")
        if args[:3] == ["docker", "compose", "up"]:
            env = _env(self.folder).get("WCA_IMAGE")
            self.env_at_up.append(env)
            return Result(0 if self.healthy or env != NEW else 1)
        if args[:3] == ["docker", "image", "prune"]:
            return Result(0)
        if args[:2] == ["systemctl", "start"]:
            return Result(0)
        raise AssertionError(f"unexpected command {args}")

    def ran(self, *prefix):
        return [c for c in self.commands if c[: len(prefix)] == list(prefix)]


def _env(folder):
    path = folder / ".env"
    if not path.exists():
        return {}
    return dict(line.split("=", 1) for line in path.read_text().splitlines() if "=" in line)


def _write_env(folder, text):
    (folder / ".env").write_text(text)


def _bad(folder):
    path = folder / "bad-images"
    return path.read_text().split() if path.exists() else []


def test_the_script_is_installed_next_to_the_compose_file():
    assert SCRIPT.exists()
    assert (ROOT / "deploy" / "compose.yaml").exists()


def test_it_pulls_the_main_image():
    assert pull_deploy.IMAGE == f"{REPO}:main"


def test_a_new_image_is_pinned_started_and_kept_when_healthy(tmp_path):
    _write_env(tmp_path, f"WCA_DATA_PING_URL=https://hc.example/ping/abc\nWCA_IMAGE={OLD}\n")
    docker = FakeDocker(tmp_path)
    assert pull_deploy.deploy(tmp_path, docker) == "deployed"
    assert docker.ran("docker", "pull") == [["docker", "pull", "-q", f"{REPO}:main"]]
    assert docker.ran("docker", "compose", "up")[0][:4] == ["docker", "compose", "up", "-d"]
    assert "--wait" in docker.ran("docker", "compose", "up")[0]
    assert docker.ran("docker", "compose", "up")[0][-1] == "web"
    assert docker.env_at_up == [NEW]
    assert _env(tmp_path) == {"WCA_DATA_PING_URL": "https://hc.example/ping/abc", "WCA_IMAGE": NEW}


def test_a_kept_image_prunes_only_this_apps_old_images(tmp_path):
    _write_env(tmp_path, f"WCA_IMAGE={OLD}\n")
    docker = FakeDocker(tmp_path)
    pull_deploy.deploy(tmp_path, docker)
    assert docker.ran("docker", "image", "prune") == [[
        "docker", "image", "prune", "--force",
        "--filter", "label=org.opencontainers.image.source=https://github.com/tdshaw2000/wca-records-analyser",
    ]]


def test_the_image_already_running_is_left_alone(tmp_path):
    _write_env(tmp_path, f"WCA_IMAGE={NEW}\n")
    docker = FakeDocker(tmp_path)
    assert pull_deploy.deploy(tmp_path, docker) == "up to date"
    assert docker.ran("docker", "compose") == []
    assert docker.ran("systemctl") == []


def test_an_unhealthy_image_is_rolled_back_and_remembered(tmp_path):
    _write_env(tmp_path, f"WCA_DATA_PING_URL=https://hc.example/ping/abc\nWCA_IMAGE={OLD}\n")
    docker = FakeDocker(tmp_path, healthy=False)
    with pytest.raises(pull_deploy.DeployFailed, match="rolled back"):
        pull_deploy.deploy(tmp_path, docker)
    assert docker.env_at_up == [NEW, OLD]
    assert _env(tmp_path) == {"WCA_DATA_PING_URL": "https://hc.example/ping/abc", "WCA_IMAGE": OLD}
    assert _bad(tmp_path) == [NEW]
    assert docker.ran("docker", "image", "prune") == []
    assert docker.ran("systemctl") == []


def test_a_new_deploy_restarts_the_data_build_so_a_schema_bump_rebuilds(tmp_path):
    _write_env(tmp_path, f"WCA_IMAGE={OLD}\n")
    docker = FakeDocker(tmp_path)
    assert pull_deploy.deploy(tmp_path, docker) == "deployed"
    assert docker.ran("systemctl", "start") == [
        ["systemctl", "start", "--no-block", "wca-data-build.service"]
    ]


def test_a_remembered_bad_image_is_not_tried_again(tmp_path):
    _write_env(tmp_path, f"WCA_IMAGE={OLD}\n")
    (tmp_path / "bad-images").write_text(NEW + "\n")
    docker = FakeDocker(tmp_path)
    assert pull_deploy.deploy(tmp_path, docker) == "skipped a known-bad image"
    assert docker.ran("docker", "compose") == []
    assert _env(tmp_path)["WCA_IMAGE"] == OLD


def test_a_failed_first_deploy_leaves_no_pin_and_remembers_the_image(tmp_path):
    docker = FakeDocker(tmp_path, healthy=False)
    with pytest.raises(pull_deploy.DeployFailed, match="nothing to roll back to"):
        pull_deploy.deploy(tmp_path, docker)
    assert "WCA_IMAGE" not in _env(tmp_path)
    assert _bad(tmp_path) == [NEW]
    assert docker.env_at_up == [NEW]


def test_a_failed_rollback_says_so(tmp_path):
    _write_env(tmp_path, f"WCA_IMAGE={OLD}\n")
    docker = FakeDocker(tmp_path, healthy=False)
    original = docker.__call__

    def nothing_starts(args):
        result = original(args)
        return Result(1) if args[:3] == ["docker", "compose", "up"] else result

    with pytest.raises(pull_deploy.DeployFailed, match="rollback to .* failed too"):
        pull_deploy.deploy(tmp_path, nothing_starts)
    assert _env(tmp_path)["WCA_IMAGE"] == OLD


def test_a_failed_pull_changes_nothing(tmp_path):
    _write_env(tmp_path, f"WCA_IMAGE={OLD}\n")
    docker = FakeDocker(tmp_path, pull_fails=True)
    with pytest.raises(pull_deploy.DeployFailed, match="pull"):
        pull_deploy.deploy(tmp_path, docker)
    assert docker.ran("docker", "compose") == []
    assert _env(tmp_path)["WCA_IMAGE"] == OLD


def test_the_digest_of_this_repository_is_used_when_the_image_has_several(tmp_path):
    other = "docker.io/someone/else@sha256:" + "c" * 64
    docker = FakeDocker(tmp_path, digests=(other, NEW))
    pull_deploy.deploy(tmp_path, docker)
    assert _env(tmp_path)["WCA_IMAGE"] == NEW


def test_an_image_without_a_digest_from_this_repository_is_not_deployed(tmp_path):
    docker = FakeDocker(tmp_path, digests=())
    with pytest.raises(pull_deploy.DeployFailed, match="digest"):
        pull_deploy.deploy(tmp_path, docker)
    assert docker.ran("docker", "compose") == []


def test_the_env_file_keeps_its_permissions(tmp_path):
    _write_env(tmp_path, f"WCA_IMAGE={OLD}\n")
    os.chmod(tmp_path / ".env", 0o600)
    pull_deploy.deploy(tmp_path, FakeDocker(tmp_path))
    assert stat.S_IMODE((tmp_path / ".env").stat().st_mode) == 0o600


def test_a_new_env_file_is_private(tmp_path):
    pull_deploy.deploy(tmp_path, FakeDocker(tmp_path))
    assert stat.S_IMODE((tmp_path / ".env").stat().st_mode) == 0o600


def test_main_reports_the_outcome_and_exits_zero(tmp_path, capsys):
    assert pull_deploy.main(tmp_path, FakeDocker(tmp_path)) == 0
    assert "deployed" in capsys.readouterr().out


def test_main_reports_a_failure_and_exits_non_zero(tmp_path, capsys):
    assert pull_deploy.main(tmp_path, FakeDocker(tmp_path, pull_fails=True)) == 1
    assert "pull" in capsys.readouterr().err
