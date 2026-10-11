"""Scissor hinges: a member set that is one continuous beam, turning on the members
it crosses (engine 0.2.68).

The model is a rail running over a cross beam: two 1 m spans A-M-B along X, the
beam through M along Z and clamped at both ends, span A-M loaded. Free to turn on
the beam about Z, the rail is a two-span continuous beam on a knife edge, which
carries qL^2/16 over the support. SI units; a member along X has local z = Z.
"""

import json

import pytest

from fers_core import (
    FERS,
    AnalysisOrder,
    DistributedLoad,
    Material,
    Member,
    MemberHinge,
    MemberSet,
    NodalSupport,
    Node,
    ScissorHinge,
)
from fers_core.members.section import Section
from fers_core.supports.supportcondition import SupportCondition
from fers_core.types.pydantic_models import ScissorHinge as ScissorHingeSchema

L, Q = 1.0, 1000.0
TARGET = Q * L**2 / 16


def rack(connection="scissor", hinge=None, beam_scale=1.0):
    """The rail on the beam. `connection` is "scissor" (4 members, the rail set
    carries `hinge`), "rigid" (4 members, no release) or "link" (the old
    workaround: a 5th, short link member from the beam to a separate rail node,
    released at its rail end by `hinge`, a MemberHinge)."""
    model = FERS()
    model.settings.analysis_options.order = AnalysisOrder.LINEAR
    steel = Material(name="S355", e_mod=210e9, g_mod=81e9, density=7850.0, yield_stress=355e6)
    rail_sec = Section(name="rail", material=steel, i_y=1e-6, i_z=1e-6, j=1e-7, area=1e-3)
    s = beam_scale
    beam_sec = Section(name="beam", material=steel, i_y=1e-4 * s, i_z=1e-4 * s, j=1e-4 * s, area=5e-3 * s)

    rail_y = 0.001 if connection == "link" else 0.0
    pinned = NodalSupport(
        displacement_conditions={
            "X": SupportCondition.fixed(),
            "Y": SupportCondition.fixed(),
            "Z": SupportCondition.fixed(),
        },
        rotation_conditions={
            "X": SupportCondition.fixed(),
            "Y": SupportCondition.free(),
            "Z": SupportCondition.free(),
        },
    )
    roller = NodalSupport(
        displacement_conditions={
            "X": SupportCondition.free(),
            "Y": SupportCondition.fixed(),
            "Z": SupportCondition.fixed(),
        },
        rotation_conditions={
            "X": SupportCondition.fixed(),
            "Y": SupportCondition.free(),
            "Z": SupportCondition.free(),
        },
    )
    a, b = Node(0.0, rail_y, 0.0), Node(2 * L, rail_y, 0.0)
    a.nodal_support, b.nodal_support = pinned, roller
    m_beam = Node(L, 0.0, 0.0)
    m_rail = Node(L, rail_y, 0.0) if connection == "link" else m_beam
    b1, b2 = Node(L, 0.0, -0.5), Node(L, 0.0, 0.5)
    b1.nodal_support = b2.nodal_support = NodalSupport()

    rail_1 = Member(start_node=a, end_node=m_rail, section=rail_sec)
    rail_2 = Member(start_node=m_rail, end_node=b, section=rail_sec)
    rail = MemberSet(members=[rail_1, rail_2], classification="Rail")
    beam = MemberSet(
        members=[
            Member(start_node=b1, end_node=m_beam, section=beam_sec),
            Member(start_node=m_beam, end_node=b2, section=beam_sec),
        ],
        classification="Beam",
    )
    if connection == "scissor":
        rail.scissor_hinge = hinge
    model.add_member_set(rail)
    model.add_member_set(beam)
    if connection == "link":
        link = Member(start_node=m_beam, end_node=m_rail, section=beam_sec, end_hinge=hinge)
        model.add_member_set(MemberSet(members=[link]))

    case = model.create_load_case(name="span 1")
    DistributedLoad(member=rail_1, load_case=case, magnitude=Q, end_magnitude=Q, direction=(0, -1, 0))
    return model, rail_1


def moment_over_m(model, rail_1):
    model.run_analysis()
    result = model.resultsbundle.loadcases["span 1"].member_results[str(rail_1.id)]
    return abs(result.local_end_forces.mz)


def test_round_trips_through_the_model():
    hinge = ScissorHinge(rotational_release_y=0.0, rotational_release_z=0.0)
    model, _ = rack(hinge=hinge)
    data = model.to_dict()

    assert data["schema_version"] == 3
    expected = {"id": hinge.id, "rotational_release_y": 0.0, "rotational_release_z": 0.0}
    assert data["model"]["scissor_hinges"] == [expected]
    rail_set = next(s for s in data["model"]["member_sets"] if s["classification"] == "Rail")
    assert rail_set["scissor_hinge"] == hinge.id

    again = FERS.from_dict(json.loads(json.dumps(data)))
    assert again.to_dict()["model"] == data["model"]
    hinge = next(s for s in again.member_sets if s.classification == "Rail").scissor_hinge
    assert isinstance(hinge, ScissorHinge)
    assert (hinge.rotational_release_x, hinge.rotational_release_y, hinge.rotational_release_z) == (
        None,
        0.0,
        0.0,
    )
    assert again.model.scissor_hinges == [hinge]


def test_a_model_without_one_is_written_as_before():
    model, _ = rack(connection="rigid")
    data = model.to_dict()
    assert "scissor_hinges" not in data["model"]
    assert data["schema_version"] == 1
    assert all("scissor_hinge" not in s for s in data["model"]["member_sets"])


def test_conforms_to_the_generated_models():
    hinge = ScissorHinge(rotational_release_z=2.5e5)
    ScissorHingeSchema(**hinge.to_dict())
    model, _ = rack(hinge=hinge)
    model.validate_schema()


def test_member_set_keeps_its_buckling_lengths_through_from_dict():
    # Written by to_dict since 0.1.9x but dropped on the way back in until 0.1.99,
    # so a model loaded from JSON lost its EC3 buckling lengths.
    model, _ = rack(connection="rigid")
    rail = model.member_sets[0]
    rail.buckling_length_y, rail.ltb_length, rail.effective_length_factor_z = 2.0, 1.5, 0.7
    again = FERS.from_dict(json.loads(json.dumps(model.to_dict())))
    back = again.member_sets[0]
    assert (back.buckling_length_y, back.ltb_length, back.effective_length_factor_z) == (2.0, 1.5, 0.7)


def test_the_rail_carries_ql2_over_16():
    model, rail_1 = rack(hinge=ScissorHinge(rotational_release_y=0.0, rotational_release_z=0.0))
    assert moment_over_m(model, rail_1) == pytest.approx(TARGET, rel=0.01)

    stiff, rail_1 = rack(hinge=ScissorHinge(rotational_release_z=0.0), beam_scale=1e3)
    assert moment_over_m(stiff, rail_1) == pytest.approx(TARGET, rel=1e-4)

    rigid, rail_1 = rack(connection="rigid")
    assert moment_over_m(rigid, rail_1) > 1.5 * TARGET


@pytest.mark.parametrize("k", [0.0, 4.0e5])
def test_agrees_with_the_link_it_replaces(k):
    """The workaround hangs the rail 1 mm above the beam on a link released at
    its rail end; the link's local y is global Z."""
    scissor, rail_s = rack(hinge=ScissorHinge(rotational_release_z=k))
    link, rail_l = rack(connection="link", hinge=MemberHinge(rotational_release_my=k))
    assert moment_over_m(scissor, rail_s) == pytest.approx(moment_over_m(link, rail_l), rel=0.005)


def test_second_order_solves():
    model, rail_1 = rack(hinge=ScissorHinge(rotational_release_z=0.0))
    model.settings.analysis_options.order = AnalysisOrder.NONLINEAR
    assert moment_over_m(model, rail_1) == pytest.approx(TARGET, rel=0.01)


def test_the_solver_refuses_a_set_that_meets_nothing():
    """Every member in one set is the layout to avoid: nothing is outside it."""
    model, _ = rack(connection="rigid")
    everything = MemberSet(
        members=[m for s in model.member_sets for m in s.members],
        scissor_hinge=ScissorHinge(rotational_release_z=0.0),
    )
    model.member_sets = [everything]
    with pytest.raises(RuntimeError, match="meets no member outside the set"):
        model.run_analysis()
