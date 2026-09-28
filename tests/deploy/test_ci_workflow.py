"""CI builds the image on every branch and publishes it to GHCR from main only; the VM pulls it."""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
CI = WORKFLOWS / "ci.yml"
IMAGE = "ghcr.io/tdshaw2000/wca-records-analyser"


def _jobs():
    return yaml.safe_load(CI.read_text())["jobs"]


def _uses(job, action):
    steps = [step for step in job["steps"] if step.get("uses", "").startswith(action + "@")]
    assert len(steps) == 1, f"expected one {action} step"
    return steps[0]


def test_the_render_deploy_is_gone():
    assert "deploy_render" not in _jobs()
    assert "RENDER" not in CI.read_text()


def test_render_yaml_is_a_static_holding_page_not_the_app():
    # The app deploys to the VM now (see docs/runbook.md); render.yaml only
    # points Render's free static-site hosting at deploy/render-holding, a
    # tiny "we've moved" page for anyone who still lands on the old Render URL.
    config = yaml.safe_load((ROOT / "render.yaml").read_text())
    (service,) = config["services"]
    assert service["runtime"] == "static"
    assert service["staticPublishPath"] == "./deploy/render-holding"
    assert service["autoDeploy"] is True
    assert "dockerfilePath" not in service


def test_every_branch_builds_the_image_and_checks_it_turns_healthy():
    image = _jobs()["image"]
    assert image["needs"] == "test"
    assert "if" not in image
    script = "\n".join(step.get("run", "") for step in image["steps"])
    assert "docker build" in script
    assert "Health.Status" in script
    assert "docker compose -f deploy/compose.yaml config" in script


def test_only_main_publishes_and_only_after_the_image_checks_pass():
    publish = _jobs()["publish"]
    assert publish["needs"] == "image"
    assert publish["if"] == "github.ref == 'refs/heads/main'"


def test_only_the_publish_job_can_write_packages():
    workflow = yaml.safe_load(CI.read_text())
    assert workflow["permissions"] == {"contents": "read"}
    for name, job in _jobs().items():
        if name == "publish":
            assert job["permissions"] == {"contents": "read", "packages": "write"}
        else:
            assert "packages" not in job.get("permissions", {}), name


def test_publish_pushes_an_arm64_image_where_the_vm_pulls_from():
    publish = _jobs()["publish"]
    login = _uses(publish, "docker/login-action")["with"]
    assert login["registry"] == "ghcr.io"
    assert login["password"] == "${{ secrets.GITHUB_TOKEN }}"
    build = _uses(publish, "docker/build-push-action")["with"]
    assert build["push"] is True
    assert "linux/arm64" in build["platforms"].split(",")
    tags = build["tags"].splitlines()
    assert f"{IMAGE}:main" in tags
    assert f"{IMAGE}:sha-${{{{ github.sha }}}}" in tags
    assert f'REPOSITORY = "{IMAGE}"' in (ROOT / "deploy" / "pull_deploy.py").read_text()


def test_no_workflow_uses_a_self_hosted_runner_pull_request_target_or_a_secret():
    for path in WORKFLOWS.glob("*.yml"):
        text = path.read_text()
        assert "pull_request_target" not in text, path.name
        assert "self-hosted" not in text, path.name
        secrets = set(re.findall(r"secrets\.(\w+)", text))
        assert secrets <= {"GITHUB_TOKEN"}, path.name
        for job in yaml.safe_load(text)["jobs"].values():
            assert job["runs-on"].startswith("ubuntu-"), path.name
