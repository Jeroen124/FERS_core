"""The model-building helpers: dead load from member weight, and model patterns."""

from collections import Counter

import pytest

from fers_core import (
    FERS,
    BucklingRestraint,
    LoadCase,
    Material,
    Member,
    MemberSet,
    MemberType,
    NodalLoad,
    NodalSupport,
    Node,
    Section,
)
from fers_core.builders import create_beam

G = 9.81


def _steel():
    return Material(name="S355", e_mod=210e9, g_mod=81e9, density=7850.0, yield_stress=355e6)


# ---------------------------------------------------------------------------
# LoadCase.apply_deadload_to_members
# ---------------------------------------------------------------------------


def test_dead_load_is_the_members_weight_spread_over_its_length():
    FERS()
    section = Section(name="box", material=_steel(), i_y=2e-5, i_z=2e-5, j=1e-6, area=2.0e-3)
    member = Member(Node(0.0, 0.0, 0.0), Node(5.0, 0.0, 0.0), section=section)
    case = LoadCase(name="Dead")

    (load,) = LoadCase.apply_deadload_to_members([member], case, (0.0, 1.0, 0.0))

    # 7850 kg/m³ x 2.0e-3 m² = 15.7 kg/m, so 154.017 N/m; 770.085 N over the 5 m.
    assert load.magnitude == pytest.approx(-154.017)
    assert load.magnitude * member.length() == pytest.approx(-member.weight * G)
    assert (load.start_frac, load.end_frac) == (0, 1)
    assert case.distributed_loads == [load]


def test_a_given_weight_is_the_members_total_mass():
    FERS()
    section = Section(name="box", material=_steel(), i_y=2e-5, i_z=2e-5, j=1e-6, area=2.0e-3)
    member = Member(Node(0.0, 0.0, 0.0), Node(5.0, 0.0, 0.0), section=section, weight=500.0)
    (load,) = LoadCase.apply_deadload_to_members([member], LoadCase(name="Dead"), "Y")
    assert load.magnitude == pytest.approx(-G * 100.0)  # 500 kg over 5 m
    assert load.direction == (0.0, 1.0, 0.0)


def test_dead_load_direction_must_be_a_vector_or_an_axis():
    FERS()
    member = Member(Node(0.0, 0.0, 0.0), Node(1.0, 0.0, 0.0), member_type=MemberType.RIGID)
    with pytest.raises(ValueError, match="X, Y, Z"):
        LoadCase.apply_deadload_to_members([member], LoadCase(name="Dead"), "W")


def test_dead_load_reactions_equal_the_solvers_own_self_weight():
    helper = create_beam(5.0, "IPE180")
    LoadCase.apply_deadload_to_members(helper.members, helper.load_cases[0], "Y")
    helper.run_analysis()
    applied = sum(r.nodal_forces.fy for r in helper.resultsbundle.loadcases["Load"].reaction_nodes.values())

    solver = create_beam(5.0, "IPE180")
    solver.settings.analysis_options.enable_self_weight = True
    solver.run_analysis()
    computed = solver.resultsbundle.loadcases["Self-weight"].reaction_nodes.values()

    mass = sum(member.weight for member in helper.members)
    assert applied == pytest.approx(mass * G, rel=1e-9)
    assert applied == pytest.approx(sum(r.nodal_forces.fy for r in computed), rel=1e-9)


# ---------------------------------------------------------------------------
# FERS.create_combined_model_pattern
# ---------------------------------------------------------------------------


def _portal() -> FERS:
    model = FERS()
    steel = _steel()
    section = Section(name="box", material=steel, i_y=2e-5, i_z=2e-5, j=1e-6, area=5e-3)
    left_base = Node(0.0, 0.0, 0.0, nodal_support=NodalSupport())
    left_top = Node(0.0, 3.0, 0.0)
    right_top = Node(4.0, 3.0, 0.0)
    right_base = Node(4.0, 0.0, 0.0, nodal_support=NodalSupport())
    column = Member(left_base, left_top, section=section)
    beam = Member(left_top, right_top, section=section, end_offset={"Y": -0.1}, reference_member=column)
    other_column = Member(right_base, right_top, section=section)
    tie = Member(left_base, right_top, section=section, member_type=MemberType.TENSION)
    bracket = Member(right_top, Node(4.0, 3.0, 0.5), member_type=MemberType.RIGID)
    model.add_member_set(
        MemberSet(
            members=[column, beam, other_column, tie, bracket],
            buckling_restraints=[BucklingRestraint(left_top.id, restrains_local_y=True)],
            buckling_length_y=3.0,
        )
    )
    return model


def test_every_copy_of_a_pattern_has_its_own_ids():
    original = _portal()
    original_members = original.get_all_members()
    original_nodes = original.get_all_nodes()

    combined = FERS.create_combined_model_pattern(original, 3, (5.0, 0.0, 0.0))

    members = combined.get_all_members()
    nodes = combined.get_all_nodes()
    assert len(combined.member_sets) == 3
    assert len(members) == 3 * len(original_members)
    assert len({member.id for member in members}) == len(members)
    # The solver needs node ids 1..n without gaps.
    assert sorted(node.id for node in nodes) == list(range(1, 3 * len(original_nodes) + 1))
    assert [member.id for member in original_members] == [member.id for member in members[:5]]
    assert Counter(member.member_type for member in members) == Counter(
        {MemberType.NORMAL: 9, MemberType.TENSION: 3, MemberType.RIGID: 3}
    )

    new_node = Node(0.0, 9.0, 0.0)
    assert new_node.id not in {node.id for node in nodes}


def test_a_copy_refers_to_its_own_members_and_nodes():
    combined = FERS.create_combined_model_pattern(_portal(), 3, (5.0, 0.0, 0.0))
    for member_set in combined.member_sets:
        column, beam = member_set.members[:2]
        assert beam.reference_member is column
        assert beam.end_offset == {"X": 0.0, "Y": -0.1, "Z": 0.0}
        (restraint,) = member_set.buckling_restraints
        assert restraint.node_id == column.end_node.id
        assert member_set.buckling_length_y == 3.0
    x_of_left_base = [member_set.members[0].start_node.X for member_set in combined.member_sets]
    assert x_of_left_base == [0.0, 5.0, 10.0]


def test_a_pattern_keeps_the_originals_settings_and_solves():
    original = _portal()
    original.settings.unit_settings.force_unit = "kN"
    combined = FERS.create_combined_model_pattern(original, 2, (5.0, 0.0, 0.0))
    assert combined.settings is not original.settings
    assert combined.settings.unit_settings.force_unit == "kN"

    load = combined.create_load_case("Wind")
    NodalLoad(combined.member_sets[1].members[1].end_node, load, 1.0, (1.0, 0.0, 0.0))
    combined.run_analysis()
    reactions = combined.resultsbundle.loadcases["Wind"].reaction_nodes
    assert sum(r.nodal_forces.fx for r in reactions.values()) == pytest.approx(-1.0)
