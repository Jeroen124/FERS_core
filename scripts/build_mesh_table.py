"""Mesh every catalogue geometry and write fers_core/members/mesh_table.json.gz.

`pip install FERS` has no sectionproperties since 0.2.0, so catalogue sections read
their meshed properties from this table (see fers_core/members/_mesh_table.py).
Rebuild it after changing a Section factory, `Section._extract_advanced_props`, the
catalogue, or the sectionproperties pin; tests/members/test_mesh_table.py fails
until you do. Build with the pinned versions, as CI tests with them:

    pip install -r requirements.txt
    python scripts/build_mesh_table.py

A newer sectionproperties moves values in the last digits, and FERS_cloud pins some
EN values exactly (see scripts/export_sections.py).
"""

from __future__ import annotations

import os
import sys
import time
from importlib import metadata

# Allow `python scripts/build_mesh_table.py` from the repo root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fers_core import Material, Section, list_sections  # noqa: E402
from fers_core.members import _mesh_table  # noqa: E402

# f_y only moves the EC3 block, which is not in the table.
_STEEL = Material(name="S235", e_mod=210e9, g_mod=81e9, density=7850, yield_stress=235e6)


def build() -> dict[str, dict]:
    """Mesh every geometry the catalogue uses, bypassing the shipped table."""
    _mesh_table.recording = {}
    try:
        for name in list_sections():
            Section.from_name(name, _STEEL)
        return _mesh_table.recording
    finally:
        _mesh_table.recording = None


def main() -> int:
    started = time.perf_counter()
    table = build()
    path = os.path.join(os.path.dirname(_mesh_table.__file__), _mesh_table.TABLE_FILE)
    provenance = {
        "generator": "scripts/build_mesh_table.py",
        "sectionproperties": metadata.version("sectionproperties"),
    }
    _mesh_table.write(path, table, provenance)
    seconds = time.perf_counter() - started
    print(f"{len(table)} geometries from {len(list_sections())} sections in {seconds:.0f} s -> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
