"""JSON helpers: NaN/inf are not valid JSON, so they are written as null."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np


def clean(o):
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (float, np.floating)):
        return None if not math.isfinite(float(o)) else float(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o


def dump(obj, path: Path, indent: int | None = None) -> None:
    Path(path).write_text(json.dumps(clean(obj), indent=indent, allow_nan=False))
