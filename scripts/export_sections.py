"""Export the EN steel section library to JSON for non-Python consumers.

The FERS section geometry lives in Python (dimensions in ``steel_sections_en.py``,
properties computed by ``sectionproperties`` via ``Section.from_name``). This
script dumps every named section's computed geometry to a single JSON so the
TypeScript cloud / builders can offer named sections (IPE, HEA, RHS, …) without a
Python round-trip. The Python library stays the single source of the data.

Geometry only — elastic/plastic section moduli (wel/wpl) and EC3 params (buckling
curves, section class) are NOT computed here; add them when the cloud needs a full
EC3 member check.

Usage::

    python scripts/export_sections.py [output.json]
"""

from __future__ import annotations

import json
import os
import sys
import time

# Allow `python scripts/export_sections.py` from the repo root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fers_core import list_sections, Section, Material  # noqa: E402

# f_y is irrelevant to geometry; any grade gives the same section properties.
_STEEL = Material(name="S235", e_mod=210e9, g_mod=81e9, density=7850, yield_stress=235e6)

# Geometry fields to keep from Section.to_dict() (drop per-model id/material/name/shape_path).
_GEOM_KEYS = [
    "area",
    "i_y",
    "i_z",
    "j",
    "i_w",
    "a_sy",
    "a_sz",
    "wel_y",
    "wel_z",
    "wpl_y",
    "wpl_z",
    "h",
    "b",
    "y_s",
    "z_s",
    "wagner_coeff",
    "centroid_y",
    "centroid_z",
]

_DEFAULT_OUT = "fers_core/sections/steel_sections.generated.json"


def main() -> int:
    out_path = sys.argv[1] if len(sys.argv) > 1 else _DEFAULT_OUT
    names = list_sections()
    result: dict[str, dict] = {}
    skipped: list[str] = []
    t0 = time.time()

    for i, name in enumerate(names):
        try:
            d = Section.from_name(name, _STEEL).to_dict()
            result[name] = {k: d[k] for k in _GEOM_KEYS if d.get(k) is not None}
        except Exception as exc:  # noqa: BLE001 - report and continue
            skipped.append(name)
            print(f"  skip {name}: {type(exc).__name__}: {exc}", file=sys.stderr)
        if (i + 1) % 50 == 0:
            print(f"  {i + 1}/{len(names)} ({time.time() - t0:.0f}s)", file=sys.stderr)

    payload = {
        "_generated_by": "fers_core scripts/export_sections.py",
        "_units": "SI (metres; area m^2; second moments m^4; warping m^6)",
        "_note": (
            "Geometry + elastic/plastic section moduli (wel/wpl). EC3 params "
            "(buckling curves, section class) are NOT included — the solver "
            "defaults the class from wpl presence and buckling curves to B."
        ),
        "sections": result,
    }
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=1, sort_keys=True)

    print(f"wrote {len(result)} sections to {out_path} ({len(skipped)} skipped) in {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
