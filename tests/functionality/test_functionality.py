from fers_core import (
    Node,
    Member,
    FERS,
    MemberSet,
    NodalSupport,
    NodalLoad,
    MemberHinge,
    SupportCondition,
)
from tests.common_functions import (
    build_steel_s235,
    build_ipe180,
    TOL,
    assert_close,
    cantilever_end_point_load_deflection_at_free_end,
    cantilever_end_point_load_fixed_end_moment_magnitude,
)

# Strong-axis second moment used by your helpers (about local z for vertical loading)
SECOND_MOMENT_STRONG_AXIS_IN_M4 = 10.63e-6


def test_041_rigid_member_end_load():
    steel = build_steel_s235()
    section = build_ipe180(steel)

    L_elastic = 5.0
    L_rigid = 5.0
    force_newton = 1000.0
    r_x = L_rigid  # vector from node 2 to node 3 along +X

    calculation = FERS()

    node_1 = Node(0.0, 0.0, 0.0)  # fixed
    node_2 = Node(L_elastic, 0.0, 0.0)  # end of elastic span
    node_3 = Node(L_elastic + L_rigid, 0.0, 0.0)  # end of rigid link
    node_1.nodal_support = NodalSupport()  # fully fixed

    member_elastic = Member(start_node=node_1, end_node=node_2, section=section)
    member_rigid = Member(start_node=node_2, end_node=node_3, member_type="RIGID")
    calculation.add_member_set(MemberSet(members=[member_elastic, member_rigid]))

    load_case = calculation.create_load_case(name="End Load")
    NodalLoad(node=node_2, load_case=load_case, magnitude=force_newton, direction=(0.0, -1.0, 0.0))

    calculation.run_analysis()
    results = calculation.results.loadcases["End Load"]

    dy_2 = results.displacement_nodes["2"].dy
    dy_3 = results.displacement_nodes["3"].dy
    rz_2 = results.displacement_nodes["2"].rz
    rz_3 = results.displacement_nodes["3"].rz
    mz_1 = results.reaction_nodes["1"].nodal_forces.mz

    dy_expected = cantilever_end_point_load_deflection_at_free_end(
        force_newton, L_elastic, steel.e_mod, SECOND_MOMENT_STRONG_AXIS_IN_M4
    )
    mz_expected = cantilever_end_point_load_fixed_end_moment_magnitude(force_newton, L_elastic)
    rz_expected = -force_newton * L_elastic**2 / (2.0 * steel.e_mod * SECOND_MOMENT_STRONG_AXIS_IN_M4)

    assert_close(dy_2, dy_expected, abs_tol=TOL.absolute_displacement_in_meter)

    assert_close(abs(mz_1), mz_expected, abs_tol=TOL.absolute_moment_in_newton_meter)

    absolute_rotation_tolerance = getattr(TOL, "absolute_rotation_in_radian", 1e-9)
    assert abs(rz_2 - rz_3) < absolute_rotation_tolerance
    assert abs(rz_2 - rz_expected) < absolute_rotation_tolerance

    assert_close(dy_3, dy_2 + rz_2 * r_x, abs_tol=TOL.absolute_displacement_in_meter)


def test_051_member_hinge_root_rotational_spring():
    """
    Model: node_1 --[RIGID]--> node_2 --[NORMAL + rotational spring at start]--> node_3
    Support: full fixity at node_1
    Load: downward force at node_3
    The bending span is node_2 -> node_3; the lever arm to the fixed support is node_1 -> node_3.
    """
    steel = build_steel_s235()
    section = build_ipe180(steel)

    length_rigid_meter = 2.5
    length_flexible_meter = 2.5
    force_newton = 1000.0

    calculation = FERS()

    node_1 = Node(0.0, 0.0, 0.0)
    node_2 = Node(length_rigid_meter, 0.0, 0.0)
    node_3 = Node(length_rigid_meter + length_flexible_meter, 0.0, 0.0)

    node_1.nodal_support = NodalSupport()

    # Choose k_phi_z to target a specific root rotation under the tip force
    target_root_rotation_radian = 0.1
    rotational_stiffness_k_phi_z = (force_newton * length_flexible_meter) / target_root_rotation_radian

    start_hinge = MemberHinge(hinge_type="SPRING_Z", rotational_release_mz=rotational_stiffness_k_phi_z)

    member_rigid = Member(start_node=node_1, end_node=node_2, member_type="RIGID")
    member_flexible = Member(start_node=node_2, end_node=node_3, section=section, start_hinge=start_hinge)

    calculation.add_member_set(MemberSet(members=[member_rigid, member_flexible]))

    load_case = calculation.create_load_case(name="End Load")
    NodalLoad(node=node_3, load_case=load_case, magnitude=force_newton, direction=(0.0, -1.0, 0.0))

    calculation.run_analysis()
    results = calculation.results.loadcases["End Load"]

    dy_tip_fers = results.displacement_nodes["3"].dy
    rz_tip_fers = results.displacement_nodes["3"].rz
    mz_support_fers = results.reaction_nodes["1"].nodal_forces.mz

    elastic_modulus = steel.e_mod
    moment_of_inertia = SECOND_MOMENT_STRONG_AXIS_IN_M4
    L = length_flexible_meter
    F = force_newton
    k_phi = rotational_stiffness_k_phi_z

    root_rotation_expected = (F * L) / k_phi
    tip_rotation_expected = -(
        (F * L**2) / (2.0 * elastic_modulus * moment_of_inertia) + root_rotation_expected
    )
    tip_deflection_expected = -(
        (F * L**3) / (3.0 * elastic_modulus * moment_of_inertia) + root_rotation_expected * L
    )

    # Support moment about node_1 is force times total lever arm node_1 -> node_3
    total_lever_arm = length_rigid_meter + length_flexible_meter  # equals 5.0 in this setup
    mz_support_expected_magnitude = F * total_lever_arm

    assert_close(dy_tip_fers, tip_deflection_expected, abs_tol=TOL.absolute_displacement_in_meter)

    absolute_rotation_tolerance = getattr(TOL, "absolute_rotation_in_radian", 1e-9)
    assert abs(rz_tip_fers - tip_rotation_expected) < absolute_rotation_tolerance

    assert_close(
        abs(mz_support_fers), mz_support_expected_magnitude, abs_tol=TOL.absolute_moment_in_newton_meter
    )


def test_061_two_colinear_tension_only_members_with_mid_load():
    """
    Two colinear tension-only members (node_1 -> node_2 -> node_3) with a load at node_2.
    Node_1 and node_3 are supports; node_2 is restrained in Y and Z but free in X.
    Expected:
      - Displacement u_x at node_2 equals F * L / (A * E) for the pulled side.
      - Reaction at node_1 in Fx equals -F.
      - Reaction at node_3 in Fx equals 0 (member cannot take compression).
    """
    steel = build_steel_s235()
    section = build_ipe180(steel)

    member_length_meter = 2.5
    applied_force_newton = 1.0

    calculation = FERS()

    node_1 = Node(0.0, 0.0, 0.0)
    node_2 = Node(member_length_meter, 0.0, 0.0)
    node_3 = Node(2.0 * member_length_meter, 0.0, 0.0)

    node_1.nodal_support = NodalSupport()
    node_2.nodal_support = NodalSupport(
        displacement_conditions={
            "X": SupportCondition.free(),
            "Y": SupportCondition.fixed(),
            "Z": SupportCondition.fixed(),
        }
    )
    node_3.nodal_support = NodalSupport()

    member_left = Member(start_node=node_1, end_node=node_2, section=section, member_type="TENSION")
    member_right = Member(start_node=node_2, end_node=node_3, section=section, member_type="TENSION")
    calculation.add_member_set(MemberSet(members=[member_left, member_right]))

    load_case = calculation.create_load_case(name="Mid Load")
    NodalLoad(node=node_2, load_case=load_case, magnitude=applied_force_newton, direction=(1.0, 0.0, 0.0))

    calculation.run_analysis()
    results = calculation.results.loadcases["Mid Load"]

    displacement_node_2_dx_fers = results.displacement_nodes["2"].dx
    reaction_node_1_fx_fers = results.reaction_nodes["1"].nodal_forces.fx
    reaction_node_3_fx_fers = results.reaction_nodes["3"].nodal_forces.fx

    elastic_modulus = steel.e_mod
    cross_section_area = section.area

    displacement_node_2_dx_expected = (applied_force_newton * member_length_meter) / (
        cross_section_area * elastic_modulus
    )
    reaction_node_1_fx_expected = -applied_force_newton
    reaction_node_3_fx_expected = 0.0

    assert_close(
        displacement_node_2_dx_fers,
        displacement_node_2_dx_expected,
        abs_tol=getattr(TOL, "absolute_displacement_in_meter", 1e-9),
    )

    absolute_force_tolerance = getattr(TOL, "absolute_force_in_newton", 1e-6)
    assert abs(reaction_node_1_fx_fers - reaction_node_1_fx_expected) < absolute_force_tolerance
    assert abs(reaction_node_3_fx_fers - reaction_node_3_fx_expected) < absolute_force_tolerance
