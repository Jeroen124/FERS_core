"""Older enum spellings the engine still reads, and the schema's spelling of each.

The engine accepts these through serde aliases. Its OpenAPI contract, and so the
generated input schema, lists only the canonical value. ``fers validate`` uses
this table so that it refuses only what the engine refuses: files written by
older SDKs and integrations use these spellings, and the engine solves them.
Keyed by the generated enum's name. ``tests/functionality/test_engine_aliases.py``
checks every entry against the pinned engine's own list of accepted values.
"""

from __future__ import annotations

import re
from typing import Any, Optional

ENGINE_ALIASES: dict[str, dict[str, str]] = {
    "AnalysisOrder": {
        "Linear": "LINEAR",
        "linear": "LINEAR",
        "Nonlinear": "NONLINEAR",
        "nonlinear": "NONLINEAR",
    },
    "RigidStrategy": {
        "Linear_MPC": "LinearMpc",
        "linear_mpc": "LinearMpc",
        "Rigid_Member": "RigidMember",
        "rigid_member": "RigidMember",
    },
    "NonlinearMethod": {
        "P_Delta": "P_DELTA",
        "p_delta": "P_DELTA",
        "PDelta": "P_DELTA",
        "pdelta": "P_DELTA",
        "Corotational": "COROTATIONAL",
        "corotational": "COROTATIONAL",
        "COROT": "COROTATIONAL",
        "corot": "COROTATIONAL",
    },
    "PdeltaFormulation": {
        "Consistent": "CONSISTENT",
        "consistent": "CONSISTENT",
        "Simplified": "SIMPLIFIED",
        "simplified": "SIMPLIFIED",
        "commercial": "SIMPLIFIED",
    },
    "PdeltaMode": {
        "Full": "FULL",
        "full": "FULL",
        "InPlaneOnly": "IN_PLANE_ONLY",
        "in_plane_only": "IN_PLANE_ONLY",
        "commercial": "IN_PLANE_ONLY",
    },
    "Dimensionality": {"2d": "2D", "3d": "3D"},
    "MassFormulation": {
        "Consistent": "CONSISTENT",
        "consistent": "CONSISTENT",
        "Lumped": "LUMPED",
        "lumped": "LUMPED",
    },
    "SeismicMethod": {
        "ModalResponseSpectrum": "MODAL_RESPONSE_SPECTRUM",
        "mrsa": "MODAL_RESPONSE_SPECTRUM",
        "MRSA": "MODAL_RESPONSE_SPECTRUM",
        "LateralForce": "LATERAL_FORCE",
        "lateral_force": "LATERAL_FORCE",
        "Both": "BOTH",
        "both": "BOTH",
    },
    "SpectrumType": {
        "Type1": "TYPE1",
        "type1": "TYPE1",
        "1": "TYPE1",
        "Type2": "TYPE2",
        "type2": "TYPE2",
        "2": "TYPE2",
    },
    "ModalCombination": {"Cqc": "CQC", "cqc": "CQC", "Srss": "SRSS", "srss": "SRSS"},
    "DirectionalCombination": {
        "Srss": "SRSS",
        "srss": "SRSS",
        "Percent30": "PERCENT30",
        "percent_30": "PERCENT30",
        "100_30": "PERCENT30",
    },
    "ForceUnit": {"n": "N", "kn": "kN"},
    "PressureUnit": {"pa": "Pa", "kpa": "kPa", "mpa": "MPa", "gpa": "GPa"},
    "SupportConditionType": {
        "StiffnessCurve": "Spring",
        "Positive-only": "PositiveOnly",
        "Negative-only": "NegativeOnly",
    },
    "LoadAxes": {"Global": "global", "GLOBAL": "global", "Local": "local", "LOCAL": "local"},
}


def _aliases_by_canonical_set() -> dict[frozenset[str], dict[str, str]]:
    # A pydantic enum error names the allowed values, not the enum, so the
    # table is found by its canonical set (each set is unique; the test checks).
    from fers_core.types import pydantic_models

    return {
        frozenset(member.value for member in getattr(pydantic_models, name)): aliases
        for name, aliases in ENGINE_ALIASES.items()
    }


def _canonical_for(error: dict[str, Any], table: dict[frozenset[str], dict[str, str]]) -> Optional[str]:
    if error.get("type") != "enum" or not isinstance(error.get("input"), str):
        return None
    allowed = frozenset(re.findall(r"'([^']*)'", (error.get("ctx") or {}).get("expected", "")))
    return table.get(allowed, {}).get(error["input"])


def _replace_at(document: Any, loc: tuple, value: str) -> Optional[tuple]:
    """Set the value at `loc` and return the document path it was found at, or None.

    A union's errors carry the branch's class name in `loc` (for example
    "ResponseSpectrum1"). That is no key of the document, so it is skipped.
    """
    node, path = document, []
    for i, part in enumerate(loc):
        last = i == len(loc) - 1
        found = (isinstance(part, int) and isinstance(node, list) and 0 <= part < len(node)) or (
            isinstance(node, dict) and part in node
        )
        if not found:
            if last:
                return None
            continue
        path.append(part)
        if last:
            node[part] = value
            return tuple(path)
        node = node[part]
    return None


def canonicalise_enum_spellings(document: Any, errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rewrite, in place, each enum value in `errors` that is an engine alias.

    Returns one note per rewritten value: its document path, the spelling found
    and the schema's spelling. Errors that are not aliases are left to the caller.
    """
    table = _aliases_by_canonical_set()
    notes = []
    for error in errors:
        canonical = _canonical_for(error, table)
        if canonical is None:
            continue
        path = _replace_at(document, tuple(error["loc"]), canonical)
        if path is not None:
            notes.append({"loc": path, "found": error["input"], "canonical": canonical})
    return notes
