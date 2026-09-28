"""The reference copy of the site block that lives in the scramble stack's Caddyfile."""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "deploy" / "caddy" / "wca-records-analyser.caddy"


def test_the_site_block_proxies_the_duckdns_name_to_the_web_container():
    text = SITE.read_text()
    assert re.search(r"^wca-records-analyser\.duckdns\.org \{$", text, re.MULTILINE)
    upstreams = re.findall(r"^\s*reverse_proxy (\S+)$", text, re.MULTILINE)
    compose = yaml.safe_load((ROOT / "deploy" / "compose.yaml").read_text())
    alias = compose["services"]["web"]["networks"]["edge"]["aliases"][0]
    assert upstreams == [f"{alias}:8000"]
