"""Ergonomic builders for unity-check definitions.

These return plain ``dict``s in exactly the shape the Rust solver expects on
``analysis.unity_checks`` — so you can author checks in Python and the result
flows straight through ``FERS.to_dict()`` / the solver.

Example::

    from fers_core.unity_checks import (
        generic_check, ec3_steel_check, var, member_force, section, material, expr,
    )

    calc.add_unity_check(
        generic_check(
            "bending_stress", "Bending stress σ = M·c/I",
            variables=[
                var("M", member_force("My", "MaxAbs")),
                var("c", expr("h / 2")),
                var("h", section("H")),
                var("I", section("Iy")),
                var("fy", material("Fy")),
            ],
            demand="M * c / I",
            capacity="fy",
            limit_state="ULS",
        )
    )
    calc.add_unity_check(ec3_steel_check("ec3", "EC3 steel member", limit_state="ULS"))

String enums (case-sensitive, matching the solver):
    component        N | Vy | Vz | Mx | My | Mz | Bimoment
    aggregation      MaxAbs | Max | Min | Start | End | AtFraction
    section property A·… → Area | Iy | Iz | J | Iw | WelY | WelZ | WplY | WplZ | H | B | Asy | Asz
    material         E | G | Fy | Density
    displacement     Dx | Dy | Dz | Rx | Ry | Rz | Magnitude
    limit_state      SLS | ULS | FLS | ALS
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


# ── variable sources ─────────────────────────────────────────────────────────


def member_force(component: str, aggregation: str = "MaxAbs", fraction: Optional[float] = None) -> Dict[str, Any]:
    agg: Dict[str, Any] = {"type": aggregation}
    if aggregation == "AtFraction":
        agg["fraction"] = 0.5 if fraction is None else float(fraction)
    return {"Quantity": {"MemberForce": {"component": component, "aggregation": agg}}}


def section(prop: str) -> Dict[str, Any]:
    return {"Quantity": {"Section": {"property": prop}}}


def material(prop: str) -> Dict[str, Any]:
    return {"Quantity": {"Material": {"property": prop}}}


def geometry(prop: str = "Length") -> Dict[str, Any]:
    return {"Quantity": {"Geometry": {"property": prop}}}


def displacement(component: str) -> Dict[str, Any]:
    return {"Quantity": {"Displacement": {"component": component}}}


def plate_stress(measure: str = "VonMises") -> Dict[str, Any]:
    return {"Quantity": {"PlateStress": {"measure": measure}}}


def constant(value: float) -> Dict[str, Any]:
    return {"Quantity": {"Constant": float(value)}}


def expr(expression: str) -> Dict[str, Any]:
    """A variable bound to a sub-expression over earlier variables."""
    return {"Expression": expression}


def var(name: str, source: Dict[str, Any]) -> Dict[str, Any]:
    return {"name": name, "source": source}


# ── entity selectors ─────────────────────────────────────────────────────────


def all_members() -> Dict[str, Any]:
    return {"type": "AllMembers"}


def members(ids: List[int]) -> Dict[str, Any]:
    return {"type": "Members", "ids": list(ids)}


def member_sets(ids: List[int]) -> Dict[str, Any]:
    return {"type": "MemberSets", "ids": list(ids)}


def classification(value: str) -> Dict[str, Any]:
    return {"type": "Classification", "value": value}


def all_plates() -> Dict[str, Any]:
    return {"type": "AllPlates"}


# ── check definitions ────────────────────────────────────────────────────────


def generic_check(
    id: str,
    name: str,
    *,
    demand: str,
    capacity: str,
    variables: List[Dict[str, Any]],
    applies_to: Optional[Dict[str, Any]] = None,
    limit_state: Optional[str] = None,
    load_combination_ids: Optional[List[int]] = None,
    thresholds: Optional[List[float]] = None,
    report_template: Optional[str] = None,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """A user-authored templated-formula check (utilization = demand / capacity)."""
    spec: Dict[str, Any] = {"variables": variables, "demand": demand, "capacity": capacity}
    if report_template is not None:
        spec["report_template"] = report_template
    return _check(id, name, {"Generic": spec}, applies_to, limit_state, load_combination_ids, thresholds, description)


def ec3_steel_check(
    id: str,
    name: str,
    *,
    applies_to: Optional[Dict[str, Any]] = None,
    limit_state: Optional[str] = "ULS",
    gamma_m0: float = 1.0,
    gamma_m1: float = 1.0,
    include_buckling: bool = True,
    include_ltb: bool = True,
    c1: Optional[float] = None,
    interaction_method: str = "AnnexB",
    load_combination_ids: Optional[List[int]] = None,
    thresholds: Optional[List[float]] = None,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """A built-in EN 1993-1-1 steel member check (§6.2 + §6.3)."""
    spec: Dict[str, Any] = {
        "gamma_m0": gamma_m0,
        "gamma_m1": gamma_m1,
        "include_buckling": include_buckling,
        "include_ltb": include_ltb,
        "interaction_method": interaction_method,
    }
    if c1 is not None:
        spec["c1"] = c1
    return _check(id, name, {"Ec3Steel": spec}, applies_to, limit_state, load_combination_ids, thresholds, description)


def _check(id, name, spec, applies_to, limit_state, load_combination_ids, thresholds, description):
    d: Dict[str, Any] = {
        "id": id,
        "name": name,
        "applies_to": applies_to or all_members(),
        "spec": spec,
    }
    if limit_state is not None:
        d["limit_state"] = limit_state
    if load_combination_ids:
        d["load_combination_ids"] = list(load_combination_ids)
    if thresholds is not None:
        d["thresholds"] = list(thresholds)
    if description is not None:
        d["description"] = description
    return d
