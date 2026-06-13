"""Guards that every non-Python asset the app loads at runtime is declared as
package-data, so it ships inside the installed wheel.

Regression test for the Render deploy failure: the app mounts
``wca_records_analyser/static`` via StaticFiles, which raises at import time if
the directory is absent. When the static assets were not listed in
``[tool.setuptools.package-data]`` they were omitted from the wheel, so the
container had no ``static/`` directory and the app crashed on startup.
"""

import tomllib
from pathlib import Path

from wca_records_analyser import web

PACKAGE_NAME = "wca_records_analyser"
PACKAGE_DIRECTORY = Path(web.__file__).parent
PYPROJECT_PATH = PACKAGE_DIRECTORY.parent / "pyproject.toml"
ASSET_SUFFIXES = {".html", ".css", ".js"}


def _package_data_globs():
    with open(PYPROJECT_PATH, "rb") as pyproject_file:
        config = tomllib.load(pyproject_file)
    return config["tool"]["setuptools"]["package-data"][PACKAGE_NAME]


def _runtime_asset_relative_paths():
    for asset in PACKAGE_DIRECTORY.rglob("*"):
        if asset.is_file() and asset.suffix in ASSET_SUFFIXES:
            yield asset.relative_to(PACKAGE_DIRECTORY)


def test_every_runtime_asset_is_declared_as_package_data():
    globs = _package_data_globs()
    unshipped = [
        str(asset)
        for asset in _runtime_asset_relative_paths()
        if not any(asset.match(glob) for glob in globs)
    ]
    assert not unshipped, (
        "These runtime assets are not covered by any package-data glob and "
        f"will be missing from the installed wheel: {unshipped}"
    )
