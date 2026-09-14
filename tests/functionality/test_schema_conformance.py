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
from fers_core.supports.supportcondition import SupportCondition, SupportConditionType
from fers_core.types.pydantic_models import (
    SupportConditionType as GeneratedSupportConditionType,
)
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


@pytest.mark.parametrize(
    "condition_type",
    list(SupportConditionType),
    ids=[c.name for c in SupportConditionType],
)
def test_every_support_condition_type_conforms(condition_type):
    """Every hand-written SupportConditionType must survive the schema check.

    This is the property that broke. ``SupportConditionType`` is written twice --
    by hand here, and generated from the solver's OpenAPI into
    ``types/pydantic_models.py`` -- and the two spellings disagreed:
    ``to_dict()`` emitted ``"Positive-only"`` where the generated schema accepts
    only ``"PositiveOnly"``. The Rust engine takes both, because the variants
    carry serde aliases, but a serde alias is not part of the OpenAPI document
    utoipa derives, so the SDK's own pre-flight rejected a payload its own engine
    would have solved. ``run_analysis()`` and ``run_analysis_to_file()`` both
    pre-validate, so every one-way model was refused through the documented API
    -- including the ``ground_contact_y`` preset the MCP tools hand out.

    Stated over the whole enum rather than over the two values that were wrong,
    because the instance is cheap to fix and the class is what keeps coming back.
    """
    steel = build_steel_s235()
    sec = build_ipe180(steel)
    m = FERS()
    n1 = Node(0.0, 0.0, 0.0)
    n2 = Node(5.0, 0.0, 0.0)
    n1.nodal_support = NodalSupport()

    # SPRING needs a stiffness to be a well-formed condition at all; the rest
    # are complete on their own.
    if condition_type is SupportConditionType.SPRING:
        condition = SupportCondition.spring(1.0e5)
    else:
        condition = SupportCondition(condition_type)
    n2.nodal_support = NodalSupport(displacement_conditions={"Y": condition})

    mem = Member(start_node=n1, end_node=n2, section=sec)
    m.add_member_set(MemberSet(members=[mem]))
    lc = m.create_load_case(name="LC")
    NodalLoad(node=n2, load_case=lc, magnitude=1000.0, direction=(0.0, -1.0, 0.0))
    m.validate_schema()


def test_support_condition_values_match_the_generated_enum():
    """The two spellings of the enum must be the same set, not merely both valid.

    ``test_every_support_condition_type_conforms`` catches a value the schema
    refuses. This catches the other direction -- a value the schema would accept
    that the hand-written enum no longer emits -- which no model-shaped test can
    see, because you cannot build a model out of a variant you do not have.
    """
    hand_written = {c.value for c in SupportConditionType}
    generated = {c.value for c in GeneratedSupportConditionType}
    assert hand_written == generated, (
        "SupportConditionType has drifted from the generated contract: "
        f"only hand-written {sorted(hand_written - generated)}, "
        f"only generated {sorted(generated - hand_written)}"
    )


def test_one_way_support_round_trips_through_from_dict():
    """Changing what ``to_dict()`` emits must not break reading older files.

    The canonical value moved from ``"Positive-only"`` to ``"PositiveOnly"``.
    Both spellings have to load, or every JSON model written before the change
    stops opening.
    """
    for spelling in ("PositiveOnly", "Positive-only", "positiveonly", "pos"):
        cond = SupportCondition.from_dict({"condition_type": spelling})
        assert cond.condition_type is SupportConditionType.POSITIVE_ONLY, spelling
    for spelling in ("NegativeOnly", "Negative-only", "negativeonly", "neg"):
        cond = SupportCondition.from_dict({"condition_type": spelling})
        assert cond.condition_type is SupportConditionType.NEGATIVE_ONLY, spelling

    # And the constructor-string path, which reads what to_dict() wrote.
    support = NodalSupport(displacement_conditions={"Y": "PositiveOnly"})
    assert support.displacement_conditions["Y"].condition_type is (SupportConditionType.POSITIVE_ONLY)
