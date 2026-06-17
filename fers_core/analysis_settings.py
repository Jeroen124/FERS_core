"""Ergonomic builders for the optional eigenvalue / seismic analysis blocks.

These return plain ``dict``s in exactly the shape the Rust solver expects on
``analysis.modal`` / ``analysis.buckling`` / ``analysis.seismic`` — so you can
author them in Python and the result flows straight through ``FERS.to_dict()``
and the solver.

Example::

    from fers_core.analysis_settings import (
        modal_analysis, buckling_analysis, seismic_analysis,
        eurocode_spectrum, direct_spectrum, custom_spectrum,
        load_case_ref, load_combination_ref, seismic_mass_source,
    )

    calc.analysis.set_modal(modal_analysis(num_modes=5))
    calc.analysis.set_buckling(buckling_analysis(num_modes=3, reference=load_case_ref(1)))
    calc.analysis.set_seismic(
        seismic_analysis(
            method="BOTH",
            num_modes=10,
            spectrum_x=eurocode_spectrum(ag=2.0, ground_type="B", spectrum_type="TYPE_1", q=1.5),
            mass_sources=[seismic_mass_source(gravity_lc.id, psi=1.0)],
            directions=["X", "Y"],
        )
    )

String enums (case-sensitive, matching the solver):
    mass_formulation         CONSISTENT | LUMPED
    method (seismic)         MODAL_RESPONSE_SPECTRUM | LATERAL_FORCE | BOTH
    direction                X | Y | Z
    modal_combination        CQC | SRSS
    directional_combination  SRSS | PERCENT30
    ground_type              A | B | C | D | E
    spectrum_type            TYPE1 | TYPE2
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


# ── eigen-load references (externally-tagged ``EigenLoadRef``) ────────────────


def load_case_ref(load_case_id: int) -> Dict[str, int]:
    """Reference a load case as the buckling reference load."""
    return {"LoadCase": int(load_case_id)}


def load_combination_ref(load_combination_id: int) -> Dict[str, int]:
    """Reference a load combination as the buckling reference load."""
    return {"LoadCombination": int(load_combination_id)}


# ── response spectra (externally-tagged ``ResponseSpectrum``) ─────────────────


def eurocode_spectrum(
    ag: float,
    ground_type: str,
    spectrum_type: str,
    q: float,
    beta: Optional[float] = None,
) -> Dict[str, Any]:
    """EN 1998-1 parametric spectrum (shape from ground type + spectrum type)."""
    body: Dict[str, Any] = {
        "ag": float(ag),
        "ground_type": ground_type,
        "spectrum_type": spectrum_type,
        "q": float(q),
    }
    if beta is not None:
        body["beta"] = float(beta)
    return {"EurocodeParametric": body}


def direct_spectrum(
    ag: float,
    s: float,
    tb: float,
    tc: float,
    td: float,
    q: float,
    beta: Optional[float] = None,
) -> Dict[str, Any]:
    """Direct spectrum parameters (no preset lookup); national-annex agnostic."""
    body: Dict[str, Any] = {
        "ag": float(ag),
        "s": float(s),
        "tb": float(tb),
        "tc": float(tc),
        "td": float(td),
        "q": float(q),
    }
    if beta is not None:
        body["beta"] = float(beta)
    return {"DirectParameters": body}


def custom_spectrum(points: List[List[float]]) -> Dict[str, Any]:
    """Arbitrary ``(period, spectral_acceleration)`` table [s, m/s²]."""
    return {"CustomPoints": {"points": [[float(t), float(sa)] for t, sa in points]}}


def seismic_mass_source(load_case_id: int, psi: float) -> Dict[str, Any]:
    """A gravity load case contributing to the seismic mass with factor ``psi``."""
    return {"load_case_id": int(load_case_id), "psi": float(psi)}


# ── analysis blocks ──────────────────────────────────────────────────────────


def modal_analysis(
    num_modes: int,
    *,
    mass_formulation: Optional[str] = None,
    tolerance: Optional[float] = None,
    max_iterations: Optional[int] = None,
) -> Dict[str, Any]:
    """A modal (natural-frequency) analysis request (``analysis.modal``)."""
    d: Dict[str, Any] = {"num_modes": int(num_modes)}
    if mass_formulation is not None:
        d["mass_formulation"] = mass_formulation
    if tolerance is not None:
        d["tolerance"] = float(tolerance)
    if max_iterations is not None:
        d["max_iterations"] = int(max_iterations)
    return d


def buckling_analysis(
    num_modes: int,
    reference: Dict[str, int],
    *,
    tolerance: Optional[float] = None,
    max_iterations: Optional[int] = None,
) -> Dict[str, Any]:
    """A linear (eigenvalue) buckling request (``analysis.buckling``).

    ``reference`` is an :func:`load_case_ref` / :func:`load_combination_ref`.
    """
    d: Dict[str, Any] = {"num_modes": int(num_modes), "reference": reference}
    if tolerance is not None:
        d["tolerance"] = float(tolerance)
    if max_iterations is not None:
        d["max_iterations"] = int(max_iterations)
    return d


def seismic_analysis(
    method: str,
    num_modes: int,
    spectrum_x: Dict[str, Any],
    *,
    spectrum_y: Optional[Dict[str, Any]] = None,
    spectrum_z: Optional[Dict[str, Any]] = None,
    mass_sources: Optional[List[Dict[str, Any]]] = None,
    directions: Optional[List[str]] = None,
    mass_formulation: Optional[str] = None,
    include_structural_mass: Optional[bool] = None,
    modal_combination: Optional[str] = None,
    damping: Optional[float] = None,
    directional_combination: Optional[str] = None,
    tolerance: Optional[float] = None,
    max_iterations: Optional[int] = None,
) -> Dict[str, Any]:
    """A seismic analysis request (EN 1998-1 MRSA and/or lateral force).

    ``spectrum_*`` are built with :func:`eurocode_spectrum` /
    :func:`direct_spectrum` / :func:`custom_spectrum`; ``mass_sources`` with
    :func:`seismic_mass_source`.
    """
    d: Dict[str, Any] = {
        "method": method,
        "num_modes": int(num_modes),
        "spectrum_x": spectrum_x,
    }
    if spectrum_y is not None:
        d["spectrum_y"] = spectrum_y
    if spectrum_z is not None:
        d["spectrum_z"] = spectrum_z
    if mass_sources is not None:
        d["mass_sources"] = list(mass_sources)
    if directions is not None:
        d["directions"] = list(directions)
    if mass_formulation is not None:
        d["mass_formulation"] = mass_formulation
    if include_structural_mass is not None:
        d["include_structural_mass"] = bool(include_structural_mass)
    if modal_combination is not None:
        d["modal_combination"] = modal_combination
    if damping is not None:
        d["damping"] = float(damping)
    if directional_combination is not None:
        d["directional_combination"] = directional_combination
    if tolerance is not None:
        d["tolerance"] = float(tolerance)
    if max_iterations is not None:
        d["max_iterations"] = int(max_iterations)
    return d
