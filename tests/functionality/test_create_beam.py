"""Coverage for the create_beam convenience builder (fers_core.builders)."""

import math

import pytest

from fers_core import create_beam
from tests.common_functions import build_ipe180, build_steel_s235

E = 210e9
I = 13.21e-6  # IPE180 strong-axis second moment (matches the analytical constant used across the suite)


def _ipe180():
    return build_ipe180(build_steel_s235())


def _max_abs_dy(load_case_result) -> float:
    """Largest downward deflection over all nodes (robust to node numbering)."""
    return max(abs(n.dy) for n in load_case_result.displacement_nodes.values())


def test_simply_supported_udl_matches_analytical():
    w, L = 10_000.0, 6.0
    beam = create_beam(L, _ipe180(), support="simply_supported", udl=w)
    beam.run_analysis()
    dmax = _max_abs_dy(beam.resultsbundle.loadcases["Load"])
    analytic = 5 * w * L**4 / (384 * E * I)  # mid-span
    assert math.isclose(dmax, analytic, rel_tol=0.06)


def test_cantilever_tip_point_load_matches_analytical():
    P, L = 5_000.0, 4.0
    beam = create_beam(L, _ipe180(), support="cantilever", point_load=P)
    beam.run_analysis()
    dmax = _max_abs_dy(beam.resultsbundle.loadcases["Load"])
    analytic = P * L**3 / (3 * E * I)  # free end (point_load defaults to the tip)
    assert math.isclose(dmax, analytic, rel_tol=0.08)


def test_named_section_and_schema_gate():
    # from_name path (needs sectionproperties, a declared dependency) + schema conformance.
    beam = create_beam(5.0, "IPE200", support="fixed", udl=8_000.0)
    beam.validate_schema()


def test_invalid_inputs_raise():
    with pytest.raises(ValueError):
        create_beam(-1.0, _ipe180())
    with pytest.raises(ValueError):
        create_beam(3.0, _ipe180(), support="floating")
