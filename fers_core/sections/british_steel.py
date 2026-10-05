"""British Steel UB / UC / PFC (BS EN 10365:2017) and ASTM W / HP sections.

``_british_steel_data`` holds the datasheet rows as printed, apart from the
misprints in ``CORRECTIONS``. This module names the columns and converts them to
SI; ``resolve_section`` builds the geometry from :func:`dimensions` and then
overrides the tabulated properties with :func:`published_si`, so a section matches
the datasheet rather than a re-mesh.
"""

from __future__ import annotations

from decimal import Decimal

from . import _british_steel_data as _data

CORRECTIONS = _data.CORRECTIONS

# family -> (rows, column names, catalogue). "uk" is the BS EN 10365 range, "us" the
# ASTM sheet.
FAMILIES: dict[str, tuple[dict[str, tuple], tuple[str, ...], str]] = {
    "UB": (_data.UB, _data.COLS_I, "uk"),
    "UC": (_data.UC, _data.COLS_I, "uk"),
    "PFC": (_data.PFC, _data.COLS_PFC, "uk"),
    "W": (_data.W, _data.COLS_ASTM, "us"),
    "HP": (_data.HP, _data.COLS_ASTM, "us"),
}

# Published unit -> SI. mm, cm, cm2, cm3, cm4 and dm6 (H, the warping constant).
_SI = {
    "D": "1e-3",
    "B": "1e-3",
    "t": "1e-3",
    "T": "1e-3",
    "r": "1e-3",
    "d": "1e-3",
    "Cy": "1e-2",
    "i_major": "1e-2",
    "i_minor": "1e-2",
    "A": "1e-4",
    "Wel_major": "1e-6",
    "Wel_minor": "1e-6",
    "Wpl_major": "1e-6",
    "Wpl_minor": "1e-6",
    "H": "1e-6",
    "I_major": "1e-8",
    "I_minor": "1e-8",
    "J": "1e-8",
}

_INDEX: dict[str, tuple[str, tuple, tuple[str, ...]]] = {
    name: (family, row, cols) for family, (rows, cols, _) in FAMILIES.items() for name, row in rows.items()
}


def family_of(name: str) -> str:
    return _INDEX[name][0]


def catalogue_of(name: str) -> str:
    return FAMILIES[_INDEX[name][0]][2]


def published(name: str) -> dict:
    """The datasheet row for ``name`` (a canonical key), in published units."""
    _, row, cols = _INDEX[name]
    return dict(zip(cols, row))


def published_si(name: str) -> dict:
    """The datasheet row converted to SI: m, m2, m3, m4, m6, kg/m.

    Decimal keeps the converted values short (29380 cm4 -> 0.0002938, not
    0.00029380000000000004).
    """
    out = {}
    for col, v in published(name).items():
        factor = _SI.get(col)
        out[col] = float(Decimal(repr(v)) * Decimal(factor)) if factor else v
    return out


def dimensions(name: str) -> dict:
    """Factory inputs in metres: h, b, t_w, t_f, r (and c_y for PFC, back of web to centroid)."""
    si = published_si(name)
    dims = {"h": si["D"], "b": si["B"], "t_w": si["t"], "t_f": si["T"], "r": si["r"]}
    if "Cy" in si:
        dims["c_y"] = si["Cy"]
    return dims
