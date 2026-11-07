"""Load frozen config files (policy, params, agents, catalogue)."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parent


@lru_cache
def policy() -> dict:
    return yaml.safe_load((CONFIG_DIR / "policy.yaml").read_text())["profiles"]


@lru_cache
def params() -> dict:
    return yaml.safe_load((CONFIG_DIR / "params.yaml").read_text())


@lru_cache
def agents() -> dict:
    return yaml.safe_load((CONFIG_DIR / "agents.yaml").read_text())


@lru_cache
def catalogue_raw() -> list[dict]:
    return json.loads((CONFIG_DIR / "catalogue.json").read_text())["instruments"]
