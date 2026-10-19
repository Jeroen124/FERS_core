"""Meshed properties of every catalogue profile, computed once and shipped as data.

sectionproperties (with scipy and matplotlib) is an extra since FERS 0.2.0, yet every
catalogue section takes its shear areas, shear centre, warping constant and moduli
from a mesh. Those depend on the geometry alone, so `scripts/build_mesh_table.py`
meshes each catalogue geometry once and `Section._meshed` reads the result from here.
Only a geometry outside the catalogue still needs `pip install "FERS[sections]"`.

The table is read whenever it has the geometry, with or without the extra, so a
catalogue section has the same values on every install and platform.
"""

import gzip
import json
from importlib import resources
from typing import Any, Optional

TABLE_FILE = "mesh_table.json.gz"

_table: Optional[dict[str, dict[str, Any]]] = None

# The build script sets this to a dict: the table is then bypassed, and every
# geometry meshed lands here under its key.
recording: Optional[dict[str, dict[str, Any]]] = None


def key(shape: str, params: dict[str, Any], shift: Optional[tuple[float, float]], mesh_size: float) -> str:
    """Everything that decides a meshed result. repr keeps floats exact."""
    args = [f"{k}={v!r}" for k, v in sorted(params.items())]
    return "|".join([shape, *args, f"shift={shift!r}", f"mesh={mesh_size!r}"])


def _load() -> dict[str, dict[str, Any]]:
    global _table
    if _table is None:
        try:
            data = resources.files(__package__).joinpath(TABLE_FILE).read_bytes()
        except FileNotFoundError:  # a checkout before its first build: everything meshes
            _table = {}
        else:
            _table = json.loads(gzip.decompress(data))["sections"]
    return _table


def lookup(k: str) -> Optional[dict[str, Any]]:
    """A fresh copy of the meshed properties under `k`, or None."""
    if recording is not None:
        return None
    hit = _load().get(k)
    if hit is None:
        return None
    return {name: dict(v) if isinstance(v, dict) else v for name, v in hit.items()}


def write(path: str, sections: dict[str, dict[str, Any]], provenance: dict[str, str]) -> None:
    """Write a table; `mtime=0` keeps the gzip bytes identical for identical content."""
    payload = json.dumps({**provenance, "sections": dict(sorted(sections.items()))}, separators=(",", ":"))
    with open(path, "wb") as fh:
        fh.write(gzip.compress(payload.encode("utf-8"), compresslevel=9, mtime=0))
