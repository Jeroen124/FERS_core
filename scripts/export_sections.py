"""Export the steel section library to JSON for non-Python consumers.

The FERS section geometry lives in Python. EN sections are computed by
``sectionproperties`` from the dimensions in ``steel_sections_en.py``; British Steel
and AISC sections carry their tabulated values (``british_steel.py``, ``aisc.py``).
This script dumps every
named section's geometry so the TypeScript cloud can offer named sections without a
Python round-trip. The Python library stays the single source of the data.

One file per catalogue, named as FERS_cloud's ``src/data`` expects them:

    en  steel_sections.json        EN 10365 / EN 10210 (IPE, HEA, RHS, L, ...)
    uk  steel_sections_uk.json     British Steel UB, UC, PFC
    us  steel_sections_us.json     British Steel ASTM W, HP; AISC W, HP, HSS, pipe
        steel_sections_us.meta.json

Usage::

    python scripts/export_sections.py [--catalogues en,uk,us] [--out-dir build/sections]

Copy a re-exported ``steel_sections.json`` into the cloud only when it is
byte-identical to the shipped one: a newer sectionproperties moves EN values in the
last digits, and the cloud pins some of them exactly.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

# Allow `python scripts/export_sections.py` from the repo root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fers_core import list_sections, Section, Material  # noqa: E402
from fers_core.sections import aisc, british_steel  # noqa: E402
from fers_core.sections.steel_sections_en import section_catalogue, section_source  # noqa: E402

# f_y only moves the EC3 section class; geometry is the same for every grade.
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
    # Asymmetric sections: without these the consumer sees the CENTROIDAL pair as
    # if it were principal, and every buckling check downstream is formed about
    # axes the section does not have. An L 100x100x10 stores I_y = I_z = 177 cm4
    # while its weak principal value is 73 cm4.
    "i_yz",
    "principal_axis_angle",
    # EN 1993-1-1 design parameters. Without them the solver defaults every
    # buckling curve to b - wrong for a channel (c) and for a cold-formed hollow
    # section (c) - and infers class 1 from the presence of wpl_y, which silently
    # bypasses the class 4 guard for the whole catalogue.
    "ec3",
]

# The US catalogue is picker-only in FERS Cloud: nothing resolves a W name to a
# model section, and the beam tool reads only these. A lazy chunk of 1100 rows
# should not carry shear areas, centroids and EC3 blocks nobody reads.
_US_KEYS = ["area", "i_y", "i_z", "j", "i_w", "wel_y", "wel_z", "wpl_y", "wpl_z", "h", "b"]

_FILES = {"en": "steel_sections.json", "uk": "steel_sections_uk.json", "us": "steel_sections_us.json"}

_DOCUMENTS = {
    "british_steel_uk": "British Steel UK sections datasheets (CUBD/CUCD/CPFCD:ENG:072026), "
    "https://www.britishsteel.co.uk/wp-content/uploads/2026/07/UK-sections-datasheets-20.07.26-1.pdf",
    "british_steel_us": "British Steel ASTM sections datasheet (CAWSD/CAHSD:ENG:072026), "
    "https://www.britishsteel.co.uk/wp-content/uploads/2026/07/ASTM-datasheet-20.07.26-2.pdf",
    "aisc": "AISC Shapes Database v16.0, https://cloud.aisc.org/biggie_bin/aisc-shapes-database-v160-2.xlsx",
}
_SOURCES = {"uk": ["british_steel_uk"], "us": ["british_steel_us", "aisc"]}


def _tabulated_extras(name: str) -> dict:
    """Table fields the EN record shape has no slot for (SI, mass in kg/m).

    ``source`` says whose values a row carries, so one source can be withdrawn
    without touching the other.
    """
    source = section_source(name)
    if source == "aisc":
        p = aisc.published_si(name)
        d = aisc.dimensions(name)
        extra = {"family": aisc.family_of(name), "source": "aisc"}
        if aisc.kind_of(name) == "I":
            extra.update(t_w=d["t_w"], t_f=d["t_f"], r=d["r"])
        else:
            extra["t_w"] = d["t"]
    else:
        p = british_steel.published_si(name)
        extra = {"source": "british_steel", "t_w": p["t"], "t_f": p["T"], "r": p["r"]}
        if "Cy" in p:
            extra["c_y"] = p["Cy"]
        if "non_astm" in p:
            extra.update(family=british_steel.family_of(name), non_astm_weight=p["non_astm"])
    extra["mass"] = p["mass"]
    if "w_lbft" in p:
        extra.update(w_lbft=p["w_lbft"], metric_designation=p["metric_designation"])
    return extra


def _payload(catalogue: str, sections: dict) -> dict:
    if catalogue == "en":
        return {
            "_generated_by": "fers_core scripts/export_sections.py",
            "_units": "SI (metres; area m^2; second moments m^4; warping m^6)",
            "_note": (
                "Geometry, elastic/plastic section moduli (wel/wpl), the product of "
                "inertia and principal-axis angle where the section has one, and the "
                "EN 1993-1-1 `ec3` block (section class, buckling curves, and a_eff "
                "for a class 4 section) derived by fers_core.members.ec3_section."
            ),
            "sections": sections,
        }
    return {
        "_generated_by": "fers_core scripts/export_sections.py",
        "_source": [_DOCUMENTS[s] for s in _SOURCES[catalogue]],
        "_units": "SI (metres; area m^2; second moments m^4; warping m^6; mass kg/m; w_lbft lb/ft)",
        "_note": (
            "area, i_y/i_z, j, i_w and wel/wpl are the tabulated values; i_z is the major axis. "
            "Shear areas, shear centre, centroid, the `ec3` block and a hollow section's i_w "
            "are computed from the tabulated dimensions."
        ),
        "sections": sections,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--catalogues", default="en,uk,us", help="comma-separated subset of en,uk,us")
    ap.add_argument("--out-dir", default="build/sections")
    args = ap.parse_args()
    wanted = [c.strip() for c in args.catalogues.split(",") if c.strip()]
    unknown = set(wanted) - set(_FILES)
    if unknown:
        ap.error(f"unknown catalogue(s): {', '.join(sorted(unknown))}")
    os.makedirs(args.out_dir, exist_ok=True)

    names = [n for n in list_sections() if section_catalogue(n) in wanted]
    result: dict[str, dict[str, dict]] = {c: {} for c in wanted}
    skipped: list[str] = []
    t0 = time.time()

    for i, name in enumerate(names):
        catalogue = section_catalogue(name)
        try:
            d = Section.from_name(name, _STEEL).to_dict()
            keys = _US_KEYS if catalogue == "us" else _GEOM_KEYS
            entry = {k: d[k] for k in keys if d.get(k) is not None}
            if catalogue != "en":
                entry.update(_tabulated_extras(name))
            result[catalogue][name] = entry
        except Exception as exc:  # noqa: BLE001 - report and continue
            skipped.append(name)
            print(f"  skip {name}: {type(exc).__name__}: {exc}", file=sys.stderr)
        if (i + 1) % 50 == 0:
            print(f"  {i + 1}/{len(names)} ({time.time() - t0:.0f}s)", file=sys.stderr)

    for catalogue, sections in result.items():
        path = os.path.join(args.out_dir, _FILES[catalogue])
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(_payload(catalogue, sections), f, indent=1, sort_keys=True)
        print(f"wrote {len(sections)} sections to {path}")
        if catalogue == "us":
            families: dict[str, int] = {}
            for entry in sections.values():
                families[entry["family"]] = families.get(entry["family"], 0) + 1
            meta_path = os.path.join(args.out_dir, "steel_sections_us.meta.json")
            with open(meta_path, "w", encoding="utf-8", newline="\n") as f:
                json.dump({"count": len(sections), "families": families}, f, indent=1)
                f.write("\n")

    print(f"{len(skipped)} skipped in {time.time() - t0:.0f}s")
    return 1 if skipped else 0


if __name__ == "__main__":
    raise SystemExit(main())
