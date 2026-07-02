"""Shared harness for reproducing NAFEMS benchmarks through the real FERS solver.

Why this exists
---------------
The hand-written FERS_core *input* builder does not expose modal/buckling
analysis (only static/nonlinear), and it auto-fills each member's ``weight``
field with the element *mass* (density·area·length).  The solver, however,
treats ``member.weight`` as a *force per unit length* override and derives the
modal mass as ``weight / g``.  Left alone this mis-scales every modal frequency
(observed 4.43x on a validation cantilever).  Setting ``weight = 0`` makes the
solver fall back to ``density * area`` for the mass, which reproduces closed-form
eigenfrequencies to <0.01 %.

So this harness builds model *geometry* with the normal Python API, then talks to
the exact same ``calculate_from_json`` entry point the WASM website uses -- after
(a) zeroing member weights and (b) injecting an ``analysis.modal`` /
``analysis.buckling`` request into the wire JSON.
"""

from __future__ import annotations

import copy
import json

import ujson
import fers_calculations

G_STANDARD = 9.81  # m/s^2, the solver's default gravity for weight->mass


# --- low-level solve -------------------------------------------------------


def solve_dict(model_dict: dict) -> dict:
    """Send a fully-formed model dict through the real solver, return parsed JSON."""
    d = copy.deepcopy(model_dict)
    d["results"] = None
    out = fers_calculations.calculate_from_json(ujson.dumps(d))
    return json.loads(out)


def _zero_member_weights(model_dict: dict) -> None:
    """Force the solver to derive mass from density*area instead of the (mis-scaled)
    auto-filled member.weight. Required for any correct modal/seismic result."""
    for m in model_dict.get("model", {}).get("members", []):
        m["weight"] = 0.0


# --- modal -----------------------------------------------------------------


def modal_frequencies(calc, num_modes: int = 6, mass_formulation: str = "Consistent"):
    """Return (list_of_frequencies_Hz, raw_modal_dict) for a FERS calc.

    ``calc`` is a fers_core ``FERS`` instance with geometry/supports already built.
    """
    d = calc.to_dict(include_results=False)
    _zero_member_weights(d)
    d["analysis"]["modal"] = {
        "num_modes": num_modes,
        "mass_formulation": mass_formulation,
    }
    results = solve_dict(d)["results"]
    modal = results.get("modal")
    if not modal:
        raise RuntimeError("solver returned no modal results")
    freqs = [m["natural_frequency"] for m in modal["modes"]]
    return freqs, modal


# --- static ----------------------------------------------------------------


def static_results(calc) -> dict:
    """Run the model as-built (linear static) and return the raw results dict."""
    d = calc.to_dict(include_results=False)
    return solve_dict(d)["results"]


# --- utilities -------------------------------------------------------------


def rel_err_pct(fers: float, target: float) -> float:
    denom = abs(target) if target != 0 else 1.0
    return 100.0 * abs(fers - target) / denom


def membrane_stress(n_per_m: float, thickness: float) -> float:
    """Membrane (in-plane) stress from a stress resultant N [N/m]: sigma = N / t."""
    return n_per_m / thickness


def bending_stress(m_per_m: float, thickness: float) -> float:
    """Extreme-fibre bending stress from a moment resultant M [N.m/m]: sigma = 6M / t^2."""
    return 6.0 * m_per_m / (thickness * thickness)
