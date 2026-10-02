"""deploy/collect_admin_log.py: filters the web container's access log for admin_log."""

import functools
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "deploy" / "collect_admin_log.py"

OVERVIEW_LINE = (
    'web-1  | 2026-10-02T06:46:50.123456789Z INFO:     1.2.3.4:5 - '
    '"GET /overview?wca_id=2015DOEJ01 HTTP/1.1" 200 OK'
)
HEALTHZ_LINE = (
    'web-1  | 2026-10-02T06:46:51.000000000Z INFO:     1.2.3.4:5 - '
    '"GET /healthz HTTP/1.1" 200 OK'
)


@functools.cache
def _load():
    spec = importlib.util.spec_from_file_location("collect_admin_log", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _LoadedOnUse:
    """The script as a module, loaded on first use so each test fails alone while it is missing."""

    def __getattr__(self, name):
        return getattr(_load(), name)


collect_admin_log = _LoadedOnUse()


class Result:
    def __init__(self, returncode=0, stdout=""):
        self.returncode = returncode
        self.stdout = stdout


def test_collect_keeps_only_lines_naming_a_wca_id():
    calls = []

    def run(args):
        calls.append(args)
        return Result(stdout="\n".join([OVERVIEW_LINE, HEALTHZ_LINE]))

    output_path = Path("/tmp") / "collect_admin_log_test" / "usage.log"
    try:
        count = collect_admin_log.collect(run, output_path)
        assert count == 1
        assert output_path.read_text() == OVERVIEW_LINE + "\n"
    finally:
        output_path.unlink(missing_ok=True)
        output_path.parent.rmdir()

    assert calls == [
        ["docker", "compose", "-p", "wca-records-analyser", "logs", "-t", "web"]
    ]


def test_collect_writes_an_empty_file_when_nothing_matches():
    def run(args):
        return Result(stdout=HEALTHZ_LINE)

    output_path = Path("/tmp") / "collect_admin_log_test_empty" / "usage.log"
    try:
        count = collect_admin_log.collect(run, output_path)
        assert count == 0
        assert output_path.read_text() == ""
    finally:
        output_path.unlink(missing_ok=True)
        output_path.parent.rmdir()


def test_collect_raises_when_docker_compose_logs_fails():
    def run(args):
        return Result(returncode=1, stdout="")

    try:
        collect_admin_log.collect(run, Path("/tmp/unused"))
        raise AssertionError("expected CollectFailed")
    except collect_admin_log.CollectFailed:
        pass


def test_main_prints_the_line_count_and_returns_zero(monkeypatch, capsys):
    monkeypatch.setattr(
        collect_admin_log, "collect", lambda run, output_path=None: 3
    )
    assert collect_admin_log.main() == 0
    assert "3" in capsys.readouterr().out


def test_main_prints_to_stderr_and_returns_one_on_failure(monkeypatch, capsys):
    def failing_collect(run, output_path=None):
        raise collect_admin_log.CollectFailed("docker compose logs failed")

    monkeypatch.setattr(collect_admin_log, "collect", failing_collect)
    assert collect_admin_log.main() == 1
    assert "docker compose logs failed" in capsys.readouterr().err
