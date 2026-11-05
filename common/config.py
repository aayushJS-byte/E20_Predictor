"""Load config/constants.yaml and expose sourced constants.

Code must read physical constants, limits and assumptions from here only.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONSTANTS_PATH = ROOT / "config" / "constants.yaml"
SITE_DATA = ROOT / "site" / "public" / "data"
ARTEFACTS = ROOT / "artefacts"


@lru_cache(maxsize=1)
def constants() -> dict:
    with open(CONSTANTS_PATH) as f:
        return yaml.safe_load(f)


def value(*path: str):
    """constants()['a']['b']['value'] -> value('a', 'b')."""
    node = constants()
    for p in path:
        node = node[p]
    return node["value"] if isinstance(node, dict) and "value" in node else node


def iter_entries(node=None, prefix=()):
    """Yield (dotted_key, entry) for every leaf entry that has a `source`."""
    node = constants() if node is None else node
    for k, v in node.items():
        if isinstance(v, dict) and "source" in v:
            yield ".".join(prefix + (k,)), v
        elif isinstance(v, dict):
            yield from iter_entries(v, prefix + (k,))
