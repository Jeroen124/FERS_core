"""Schema conformance: every FERS *input* model built in Python must validate
against the GENERATED pydantic ``FERS`` schema (the single source of truth,
generated from the solver's OpenAPI). Guards against a hand-written ``to_dict()``
drifting from the solver contract — the class of bug that let the analysis-order
enum and the unity-check ``report_template`` placement diverge silently.
"""

import glob
import os

import pytest

from fers_core import FERS, Node, Member, MemberSet, NodalSupport, NodalLoad
from fers_core.supports.supportcondition import SupportCondition
from fers_core.supports.stiffness_curve import ForceComponent
from fers_core.unity_checks import (
    generic_check,
    ec3_steel_check,
    var,
    member_force,
    section,
    material,
)
from tests.common_functions import build_steel_s235, build_ipe180
from tests.functionality.test_surface_loads import build_surface_model

_EXAMPLE_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "fers_core", "examples", "json_input_solver"
)
EXAMPLES = sorted(glob.glob(os.path.join(_EXAMPLE_DIR, "*.json")))


@pytest.mark.parametrize("path", EXAMPLES, ids=[os.path.basename(p) for p in EXAMPLES])
def test_example_models_conform(path):
    """Every shipped example model round-trips to a schema-conformant input."""
    FERS.from_json(path).validate_schema()


def test_examples_present():
    assert len(EXAMPLES) >= 20, "expected the example solver inputs to be present"


def _beam():
    steel = build_steel_s235()
    sec = build_ipe180(steel)
    m = FERS()
    n1 = Node(0.0, 0.0, 0.0)
    n2 = Node(5.0, 0.0, 0.0)
    n1.nodal_support = NodalSupport()
    mem = Member(start_node=n1, end_node=n2, section=sec)
    m.add_member_set(MemberSet(members=[mem]))
    lc = m.create_load_case(name="LC")
    NodalLoad(node=n2, load_case=lc, magnitude=1000.0, direction=(0.0, -1.0, 0.0))
    return m


def test_surface_load_model_conforms():
    build_surface_model().validate_schema()


def test_unity_check_model_conforms():
    m = _beam()
    m.add_unity_check(ec3_steel_check("ec3", "EC3 member", limit_state="ULS", c2=0.5, z_g=0.1))
    m.add_unity_check(
        generic_check(
            "bs",
            "Bending stress",
            variables=[
                var("M", member_force("Mz")),
                var("I", section("Iz")),
                var("fy", material("Fy")),
            ],
            demand="M/I",
            capacity="fy",
            report_template="<p>util = {{= M / I / fy}}</p>",
        )
    )
    m.validate_schema()


def test_spring_curve_support_model_conforms():
    steel = build_steel_s235()
    sec = build_ipe180(steel)
    m = FERS()
    n1 = Node(0.0, 0.0, 0.0)
    n2 = Node(5.0, 0.0, 0.0)
    n1.nodal_support = NodalSupport(
        rotation_conditions={
            "Y": SupportCondition.spring_curve(ForceComponent.My, [[0, 1e5], [1e5, 1e8]]),
        }
    )
    mem = Member(start_node=n1, end_node=n2, section=sec)
    m.add_member_set(MemberSet(members=[mem]))
    lc = m.create_load_case(name="LC")
    NodalLoad(node=n2, load_case=lc, magnitude=1000.0, direction=(0.0, -1.0, 0.0))
    m.validate_schema()


def test_invalid_model_is_rejected():
    """The gate must actually fail on drift, not silently pass."""
    m = _beam()
    m.analysis.options.order = _BadEnum()
    with pytest.raises(ValueError, match="does not conform"):
        m.validate_schema()


class _BadEnum:
    """Stand-in whose serialized value is not a valid AnalysisOrder."""

    value = "TotallyNotAnOrder"
