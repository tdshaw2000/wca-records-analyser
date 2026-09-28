"""The image the VM runs: web app and nightly build from one Dockerfile (see docs/runbook.md)."""

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = ROOT / "Dockerfile"
REPOSITORY_URL = "https://github.com/tdshaw2000/wca-records-analyser"


def _instructions():
    """(INSTRUCTION, arguments) pairs, with continuation lines joined and comments dropped."""
    text = re.sub(r"\\\n", " ", DOCKERFILE.read_text())
    pairs = []
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            keyword, _, arguments = line.partition(" ")
            pairs.append((keyword.upper(), arguments.strip()))
    return pairs


def _packages():
    with open(ROOT / "pyproject.toml", "rb") as pyproject:
        includes = tomllib.load(pyproject)["tool"]["setuptools"]["packages"]["find"]["include"]
    return [pattern.rstrip("*") for pattern in includes]


def test_every_packaged_package_is_copied_into_the_image():
    copied = {arguments.split()[0] for keyword, arguments in _instructions() if keyword == "COPY"}
    for package in _packages():
        assert package in copied, f"the Dockerfile doesn't COPY {package}"


def test_the_image_runs_as_a_non_root_user():
    instructions = _instructions()
    users = [i for i, (keyword, _) in enumerate(instructions) if keyword == "USER"]
    assert users, "no USER instruction"
    user = instructions[users[-1]][1].split(":")[0]
    assert user.isdigit() and int(user) != 0
    last_run = max(i for i, (keyword, _) in enumerate(instructions) if keyword == "RUN")
    assert users[-1] > last_run


def test_the_image_checks_its_own_health_on_the_home_page():
    healthchecks = [arguments for keyword, arguments in _instructions() if keyword == "HEALTHCHECK"]
    assert len(healthchecks) == 1
    assert "http://127.0.0.1:8000/" in healthchecks[0]


def test_the_image_names_its_source_repository():
    labels = " ".join(arguments for keyword, arguments in _instructions() if keyword == "LABEL")
    assert f"org.opencontainers.image.source={REPOSITORY_URL}" in labels


def test_the_image_carries_the_deploy_files_for_installing_on_the_vm():
    copies = [arguments.split() for keyword, arguments in _instructions() if keyword == "COPY"]
    assert ["deploy", "/opt/wca-records-analyser/deploy"] in copies


def test_bytecode_caches_anywhere_in_the_tree_stay_out_of_the_image():
    # A bare "__pycache__" only matches at the root; tests leave one in deploy/.
    patterns = (ROOT / ".dockerignore").read_text().split()
    assert "**/__pycache__" in patterns
    assert "**/*.py[cod]" in patterns
