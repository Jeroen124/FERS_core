"""AISC Shapes Database v16.0: the US shapes British Steel does not roll.

W and HP sizes missing from British Steel's ASTM datasheet, rectangular and round
HSS, and pipe. ``_aisc_data`` holds the Manual's US customary values as tabulated;
this module converts them to SI under the same keys as ``british_steel``, so
``resolve_section`` treats both sources alike.
"""

from __future__ import annotations

from decimal import Decimal

from . import _aisc_data as _data

FAMILIES: dict[str, tuple[dict[str, tuple], tuple[str, ...], str]] = {
    family: (getattr(_data, family), _data.COLS[kind], "us") for family, kind in _data.KIND.items()
}

_IN = Decimal("0.0254")
_LBFT = Decimal("0.45359237") / Decimal("0.3048")  # lb/ft -> kg/m
_SI = {
    "d": _IN,
    "bf": _IN,
    "tw": _IN,
    "tf": _IN,
    "kdes": _IN,
    "Ht": _IN,
    "B": _IN,
    "OD": _IN,
    "tdes": _IN,
    "A": _IN**2,
    "Sx": _IN**3,
    "Sy": _IN**3,
    "Zx": _IN**3,
    "Zy": _IN**3,
    "Ix": _IN**4,
    "Iy": _IN**4,
    "J": _IN**4,
    "Cw": _IN**6,
}

_INDEX: dict[str, tuple[str, tuple, tuple[str, ...]]] = {
    name: (family, row, cols) for family, (rows, cols, _) in FAMILIES.items() for name, row in rows.items()
}


def family_of(name: str) -> str:
    return _INDEX[name][0]


def kind_of(name: str) -> str:
    """``"I"`` (W, HP), ``"RECT"`` (rectangular and square HSS) or ``"ROUND"`` (round HSS, pipe)."""
    return _data.KIND[family_of(name)]


def catalogue_of(name: str) -> str:
    return "us"


def published(name: str) -> dict:
    """The Manual's row for ``name``, in US customary units."""
    _, row, cols = _INDEX[name]
    return dict(zip(cols, row))


def _si(col: str, v):
    factor = _SI.get(col)
    return float(Decimal(repr(v)) * factor) if factor is not None and v is not None else v


def published_si(name: str) -> dict:
    """The tabulated properties in SI, under the keys ``british_steel.published_si`` uses."""
    p = {col: _si(col, v) for col, v in published(name).items()}
    out = {
        "A": p["A"],
        "I_major": p["Ix"],
        "Wel_major": p["Sx"],
        "Wpl_major": p["Zx"],
        "J": p["J"],
        "H": p.get("Cw"),
        "mass": float(Decimal(repr(p["W"])) * _LBFT),
        "w_lbft": p["W"],
        "metric_designation": p["metric"],
    }
    if "Iy" in p:
        out.update(I_minor=p["Iy"], Wel_minor=p["Sy"], Wpl_minor=p["Zy"])
    else:
        out.update(I_minor=p["Ix"], Wel_minor=p["Sx"], Wpl_minor=p["Zx"])
    return out


def dimensions(name: str) -> dict:
    """Factory inputs in metres, by kind.

    I: h, b, t_w, t_f, r (r = kdes - tf, the Manual's design fillet).
    RECT: h, b, t (design wall, 0.93 x nominal for ASTM A500).
    ROUND: d, t.
    """
    p = {col: _si(col, v) for col, v in published(name).items()}
    kind = kind_of(name)
    if kind == "I":
        return {"h": p["d"], "b": p["bf"], "t_w": p["tw"], "t_f": p["tf"], "r": p["kdes"] - p["tf"]}
    if kind == "RECT":
        return {"h": p["Ht"], "b": p["B"], "t": p["tdes"]}
    return {"d": p["OD"], "t": p["tdes"]}
