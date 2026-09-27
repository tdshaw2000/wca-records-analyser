"""The data layer must stay usable by other apps, so it may never pull in the web app.

wca_data imports nothing from wca_records_analyser or the web stack. The check runs in a fresh
interpreter, because this test session has already imported the web app (see tests/conftest.py).
"""

import subprocess
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_PACKAGES = {"wca_records_analyser", "fastapi", "starlette", "jinja2", "httpx", "uvicorn"}

IMPORT_EVERY_MODULE = """
import importlib, pkgutil, sys
import wca_data
for module in pkgutil.walk_packages(wca_data.__path__, "wca_data."):
    importlib.import_module(module.name)
print("\\n".join(sorted(sys.modules)))
"""


def _modules_loaded_by_wca_data():
    completed = subprocess.run(
        [sys.executable, "-c", IMPORT_EVERY_MODULE],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert completed.returncode == 0, completed.stderr
    return completed.stdout.split()


def test_wca_data_imports_nothing_from_the_web_app_or_web_stack():
    loaded = _modules_loaded_by_wca_data()
    assert "wca_data" in loaded
    assert not [name for name in loaded if name.split(".")[0] in WEB_PACKAGES]


def test_wca_data_is_packaged_alongside_the_web_app():
    with open(REPO_ROOT / "pyproject.toml", "rb") as pyproject_file:
        config = tomllib.load(pyproject_file)
    assert "wca_data*" in config["tool"]["setuptools"]["packages"]["find"]["include"]
