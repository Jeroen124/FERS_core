from fers_core import (
    Node,
    Member,
    FERS,
    MemberSet,
    NodalSupport,
    NodalLoad,
    DistributedLoad,
    SupportCondition,
)

from fers_core.loads.distributionshape import DistributionShape
from tests.beam_equation_checks.common_functions import (
    build_steel_s235,
    build_ipe180,
    TOL,
    assert_close,
    cantilever_end_point_load_deflection_at_free_end,
    cantilever_end_point_load_fixed_end_moment_magnitude,
    cantilever_point_load_deflection_at_position_a,
    cantilever_point_load_deflection_at_free_end_from_a,
    cantilever_uniform_load_deflection_at_free_end,
    cantilever_uniform_load_fixed_end_moment,
    cantilever_full_triangular_deflection_at_free_end,
    cantilever_full_triangular_fixed_end_moment,
    cantilever_full_inverse_triangular_fixed_end_moment,
    cantilever_partial_uniform_resultant_and_fixed_moment,
    cantilever_partial_triangular_resultant_and_fixed_moment,
    simply_supported_center_point_load_deflection_at_midspan,
    simply_supported_center_point_load_max_moment,
    simply_supported_reactions_for_point_load_at_x,
    simply_supported_symmetric_double_load_mid_moment,
)

# Constant used for analytical formulas (strong axis inertia in your examples)
SECOND_MOMENT_STRONG_AXIS_IN_M4 = 10.63e-6

# 001_Cantilever_with_End_Load -------------------------------------------------


def test_001_Cantilever_with_End_Load():
    steel = build_steel_s235()
    section = build_ipe180(steel)

    beam_length_in_meter = 5.0
    force_in_newton = 1000.0

    calculation = FERS()
    node_fixed = Node(0.0, 0.0, 0.0)
    node_free = Node(beam_length_in_meter, 0.0, 0.0)
    node_fixed.nodal_support = NodalSupport()

    member = Member(start_node=node_fixed, end_node=node_free, section=section)
    calculation.add_member_set(MemberSet(members=[member]))

    load_case = calculation.create_load_case(name="End Load")
    NodalLoad(node=node_free, load_case=load_case, magnitude=force_in_newton, direction=(0.0, -1.0, 0.0))

    calculation.run_analysis()
    results = calculation.results.loadcases["End Load"]

    fers_dy_free = results.displacement_nodes["2"].dy
    fers_mz_fixed = results.reaction_nodes["1"].nodal_forces.mz

    expected_dy_free = cantilever_end_point_load_deflection_at_free_end(
        force_in_newton, beam_length_in_meter, steel.e_mod, SECOND_MOMENT_STRONG_AXIS_IN_M4
    )
    expected_mz_fixed_magnitude = cantilever_end_point_load_fixed_end_moment_magnitude(
        force_in_newton, beam_length_in_meter
    )

    assert_close(fers_dy_free, expected_dy_free, abs_tol=TOL.absolute_displacement_in_meter)
    assert_close(abs(fers_mz_fixed), expected_mz_fixed_magnitude, abs_tol=TOL.absolute_moment_in_newton_meter)


# 002_Cantilever_with_Intermediate_Load ---------------------------------------


def test_002_Cantilever_with_Intermediate_Load():
    steel = build_steel_s235()
    section = build_ipe180(steel)

    beam_length_in_meter = 5.0
    position_a_in_meter = 3.0
    force_in_newton = 1000.0

    calculation = FERS()
    node_fixed = Node(0.0, 0.0, 0.0)
    node_load = Node(position_a_in_meter, 0.0, 0.0)
    node_free = Node(beam_length_in_meter, 0.0, 0.0)
    node_fixed.nodal_support = NodalSupport()

    m1 = Member(start_node=node_fixed, end_node=node_load, section=section)
    m2 = Member(start_node=node_load, end_node=node_free, section=section)
    calculation.add_member_set(MemberSet(members=[m1, m2]))

    load_case = calculation.create_load_case(name="Intermediate Load")
    NodalLoad(node=node_load, load_case=load_case, magnitude=force_in_newton, direction=(0.0, -1.0, 0.0))

    calculation.run_analysis()
    res = calculation.results.loadcases["Intermediate Load"]

    fers_dy_at_a = res.displacement_nodes["2"].dy
    fers_dy_at_L = res.displacement_nodes["3"].dy
    fers_mz_fixed = res.reaction_nodes["1"].nodal_forces.mz

    expected_dy_at_a = cantilever_point_load_deflection_at_position_a(
        force_in_newton, position_a_in_meter, steel.e_mod, SECOND_MOMENT_STRONG_AXIS_IN_M4
    )
    expected_dy_at_L = cantilever_point_load_deflection_at_free_end_from_a(
        force_in_newton,
        beam_length_in_meter,
        position_a_in_meter,
        steel.e_mod,
        SECOND_MOMENT_STRONG_AXIS_IN_M4,
    )
    expected_mz_fixed_magnitude = force_in_newton * position_a_in_meter

    assert_close(fers_dy_at_a, expected_dy_at_a, abs_tol=TOL.absolute_displacement_in_meter)
    assert_close(fers_dy_at_L, expected_dy_at_L, abs_tol=TOL.absolute_displacement_in_meter)
    assert_close(abs(fers_mz_fixed), expected_mz_fixed_magnitude, abs_tol=TOL.absolute_moment_in_newton_meter)


# 003_Cantilever_with_Uniform_Distributed_Load --------------------------------


def test_003_Cantilever_with_Uniform_Distributed_Load():
    steel = build_steel_s235()
    section = build_ipe180(steel)

    beam_length_in_meter = 5.0
    load_intensity_in_newton_per_meter = 1000.0

    calculation = FERS()
    n1 = Node(0.0, 0.0, 0.0)
    n2 = Node(beam_length_in_meter, 0.0, 0.0)
    n1.nodal_support = NodalSupport()
    member = Member(start_node=n1, end_node=n2, section=section)
    calculation.add_member_set(MemberSet(members=[member]))

    lc = calculation.create_load_case(name="Uniform Load")
    DistributedLoad(
        member=member, load_case=lc, magnitude=load_intensity_in_newton_per_meter, direction=(0.0, -1.0, 0.0)
    )

    calculation.run_analysis()
    res = calculation.results.loadcases["Uniform Load"]

    fers_dy_L = res.displacement_nodes["2"].dy
    fers_mz_fixed = res.reaction_nodes["1"].nodal_forces.mz

    expected_dy_L = cantilever_uniform_load_deflection_at_free_end(
        load_intensity_in_newton_per_meter, beam_length_in_meter, steel.e_mod, SECOND_MOMENT_STRONG_AXIS_IN_M4
    )
    expected_mz_fixed = cantilever_uniform_load_fixed_end_moment(
        load_intensity_in_newton_per_meter, beam_length_in_meter
    )

    assert_close(fers_dy_L, expected_dy_L, abs_tol=TOL.absolute_displacement_in_meter)
    assert_close(abs(fers_mz_fixed), expected_mz_fixed, abs_tol=TOL.absolute_moment_in_newton_meter)


# 004_Cantilever_with_Partial_Uniform_Distributed_Load ------------------------


def test_004_Cantilever_with_Partial_Uniform_Distributed_Load():
    steel = build_steel_s235()
    section = build_ipe180(steel)

    beam_length_in_meter = 5.0
    load_intensity_in_newton_per_meter = 1000.0
    start_fraction = 0.4
    end_fraction = 0.7

    calculation = FERS()
    n1 = Node(0.0, 0.0, 0.0)
    n2 = Node(beam_length_in_meter, 0.0, 0.0)
    n1.nodal_support = NodalSupport()
    member = Member(start_node=n1, end_node=n2, section=section)
    calculation.add_member_set(MemberSet(members=[member]))

    lc = calculation.create_load_case(name="Partial Uniform Load")
    DistributedLoad(
        member=member,
        load_case=lc,
        magnitude=load_intensity_in_newton_per_meter,
        direction=(0.0, -1.0, 0.0),
        start_frac=start_fraction,
        end_frac=end_fraction,
    )

    calculation.run_analysis()
    res = calculation.results.loadcases["Partial Uniform Load"]

    fers_fy_fixed = res.reaction_nodes["1"].nodal_forces.fy
    fers_mz_fixed = res.reaction_nodes["1"].nodal_forces.mz

    expected_resultant, expected_mz_fixed = cantilever_partial_uniform_resultant_and_fixed_moment(
        load_intensity_in_newton_per_meter, beam_length_in_meter, start_fraction, end_fraction
    )

    assert_close(fers_fy_fixed, expected_resultant, abs_tol=TOL.absolute_force_in_newton)
    assert_close(abs(fers_mz_fixed), expected_mz_fixed, abs_tol=TOL.absolute_moment_in_newton_meter)


# 005_Cantilever_with_Triangular_Distributed_Load -----------------------------


def test_005_Cantilever_with_Triangular_Distributed_Load():
    steel = build_steel_s235()
    section = build_ipe180(steel)

    beam_length_in_meter = 5.0
    load_intensity_in_newton_per_meter = 1000.0

    calculation = FERS()
    n1 = Node(0.0, 0.0, 0.0)
    n2 = Node(beam_length_in_meter, 0.0, 0.0)
    n1.nodal_support = NodalSupport()
    member = Member(start_node=n1, end_node=n2, section=section)
    calculation.add_member_set(MemberSet(members=[member]))

    lc_tri = calculation.create_load_case(name="Triangular Load")
    lc_inv = calculation.create_load_case(name="Inverse Triangular Load")

    DistributedLoad(
        member=member,
        load_case=lc_tri,
        distribution_shape=DistributionShape.TRIANGULAR,
        magnitude=load_intensity_in_newton_per_meter,
        direction=(0.0, -1.0, 0.0),
    )
    DistributedLoad(
        member=member,
        load_case=lc_inv,
        distribution_shape=DistributionShape.INVERSE_TRIANGULAR,
        magnitude=load_intensity_in_newton_per_meter,
        direction=(0.0, -1.0, 0.0),
    )

    calculation.run_analysis()
    res_tri = calculation.results.loadcases["Triangular Load"]
    res_inv = calculation.results.loadcases["Inverse Triangular Load"]

    fers_dy_L_tri = res_tri.displacement_nodes["2"].dy
    fers_mz_fixed_tri = res_tri.reaction_nodes["1"].nodal_forces.mz
    fers_mz_fixed_inv = res_inv.reaction_nodes["1"].nodal_forces.mz

    expected_dy_L_tri = cantilever_full_triangular_deflection_at_free_end(
        load_intensity_in_newton_per_meter, beam_length_in_meter, steel.e_mod, SECOND_MOMENT_STRONG_AXIS_IN_M4
    )
    expected_mz_fixed_tri = cantilever_full_triangular_fixed_end_moment(
        load_intensity_in_newton_per_meter, beam_length_in_meter
    )
    expected_mz_fixed_inv = cantilever_full_inverse_triangular_fixed_end_moment(
        load_intensity_in_newton_per_meter, beam_length_in_meter
    )

    assert_close(fers_dy_L_tri, expected_dy_L_tri, abs_tol=TOL.absolute_displacement_in_meter)
    assert_close(abs(fers_mz_fixed_tri), expected_mz_fixed_tri, abs_tol=TOL.absolute_moment_in_newton_meter)
    assert_close(abs(fers_mz_fixed_inv), expected_mz_fixed_inv, abs_tol=TOL.absolute_moment_in_newton_meter)


# 006_Cantilever_with_Partial_Triangular_Distributed_Load ---------------------


def test_006_Cantilever_with_Partial_Triangular_Distributed_Load():
    steel = build_steel_s235()
    section = build_ipe180(steel)

    beam_length_in_meter = 5.0
    load_intensity_in_newton_per_meter = 1000.0

    calculation = FERS()
    n1 = Node(0.0, 0.0, 0.0)
    n2 = Node(beam_length_in_meter, 0.0, 0.0)
    n1.nodal_support = NodalSupport()
    member = Member(start_node=n1, end_node=n2, section=section)
    calculation.add_member_set(MemberSet(members=[member]))

    lc_tri = calculation.create_load_case(name="Triangular Load")
    lc_inv = calculation.create_load_case(name="Inverse Triangular Load")

    DistributedLoad(
        member=member,
        load_case=lc_tri,
        distribution_shape=DistributionShape.TRIANGULAR,
        magnitude=load_intensity_in_newton_per_meter,
        direction=(0.0, -1.0, 0.0),
        start_frac=0.0,
        end_frac=0.6,
    )
    DistributedLoad(
        member=member,
        load_case=lc_inv,
        distribution_shape=DistributionShape.INVERSE_TRIANGULAR,
        magnitude=load_intensity_in_newton_per_meter,
        direction=(0.0, -1.0, 0.0),
        start_frac=0.3,
        end_frac=0.7,
    )

    calculation.run_analysis()
    res_tri = calculation.results.loadcases["Triangular Load"]
    res_inv = calculation.results.loadcases["Inverse Triangular Load"]

    fers_fy_fixed_tri = res_tri.reaction_nodes["1"].nodal_forces.fy
    fers_fy_fixed_inv = res_inv.reaction_nodes["1"].nodal_forces.fy
    fers_mz_fixed_tri = res_tri.reaction_nodes["1"].nodal_forces.mz
    fers_mz_fixed_inv = res_inv.reaction_nodes["1"].nodal_forces.mz

    expected_resultant_tri, expected_mz_tri = cantilever_partial_triangular_resultant_and_fixed_moment(
        load_intensity_in_newton_per_meter, beam_length_in_meter, 0.0, 0.6, inverse=False
    )
    expected_resultant_inv, expected_mz_inv = cantilever_partial_triangular_resultant_and_fixed_moment(
        load_intensity_in_newton_per_meter, beam_length_in_meter, 0.3, 0.7, inverse=True
    )

    assert_close(fers_fy_fixed_tri, expected_resultant_tri, abs_tol=TOL.absolute_force_in_newton)
    assert_close(fers_fy_fixed_inv, expected_resultant_inv, abs_tol=TOL.absolute_force_in_newton)
    assert_close(abs(fers_mz_fixed_tri), expected_mz_tri, abs_tol=TOL.absolute_moment_in_newton_meter)
    assert_close(abs(fers_mz_fixed_inv), expected_mz_inv, abs_tol=TOL.absolute_moment_in_newton_meter)


# 007_Cantilever_with_End_Moment ----------------------------------------------


def test_007_Cantilever_with_End_Moment():
    steel = build_steel_s235()
    section = build_ipe180(steel)

    beam_length_in_meter = 5.0
    end_moment_in_newton_meter = 500.0

    from fers_core.loads.nodalmoment import NodalMoment

    calculation = FERS()
    n1 = Node(0.0, 0.0, 0.0)
    n2 = Node(beam_length_in_meter, 0.0, 0.0)
    n1.nodal_support = NodalSupport()
    member = Member(start_node=n1, end_node=n2, section=section)
    calculation.add_member_set(MemberSet(members=[member]))

    lc = calculation.create_load_case(name="End Moment")
    NodalMoment(node=n2, load_case=lc, magnitude=end_moment_in_newton_meter, direction=(0.0, 0.0, 1.0))

    calculation.run_analysis()
    res = calculation.results.loadcases["End Moment"]

    fers_dy_L = res.displacement_nodes["2"].dy
    fers_mz_fixed = res.reaction_nodes["1"].nodal_forces.mz

    expected_deflection = (end_moment_in_newton_meter * beam_length_in_meter**2) / (
        2.0 * steel.e_mod * SECOND_MOMENT_STRONG_AXIS_IN_M4
    )
    expected_reaction_moment_magnitude = end_moment_in_newton_meter

    assert_close(fers_dy_L, expected_deflection, abs_tol=TOL.absolute_displacement_in_meter)
    assert_close(
        abs(fers_mz_fixed), expected_reaction_moment_magnitude, abs_tol=TOL.absolute_moment_in_newton_meter
    )


# 011_Simply_Supported_with_Center_Load ---------------------------------------


def test_011_Simply_Supported_with_Center_Load():
    steel = build_steel_s235()
    section = build_ipe180(steel)

    total_length_in_meter = 6.0
    mid_position_in_meter = total_length_in_meter / 2.0
    force_in_newton = 1000.0

    calculation = FERS()
    n_left = Node(0.0, 0.0, 0.0)
    n_mid = Node(mid_position_in_meter, 0.0, 0.0)
    n_right = Node(total_length_in_meter, 0.0, 0.0)

    simple_support = NodalSupport(
        rotation_conditions={
            "X": SupportCondition.fixed(),
            "Y": SupportCondition.free(),
            "Z": SupportCondition.free(),
        }
    )
    n_left.nodal_support = simple_support
    n_right.nodal_support = simple_support

    m1 = Member(start_node=n_left, end_node=n_mid, section=section)
    m2 = Member(start_node=n_mid, end_node=n_right, section=section)
    calculation.add_member_set(MemberSet(members=[m1, m2]))

    lc = calculation.create_load_case(name="Center Load")
    NodalLoad(node=n_mid, load_case=lc, magnitude=force_in_newton, direction=(0.0, -1.0, 0.0))

    calculation.run_analysis()
    res = calculation.results.loadcases["Center Load"]

    fers_dy_mid = res.displacement_nodes["2"].dy
    fers_mz_left = res.reaction_nodes["1"].nodal_forces.mz
    fers_mz_right = res.reaction_nodes["3"].nodal_forces.mz
    fers_mz_member_mid = res.member_results["1"].end_node_forces.mz  # internal at mid

    expected_dy_mid = simply_supported_center_point_load_deflection_at_midspan(
        force_in_newton, total_length_in_meter, steel.e_mod, SECOND_MOMENT_STRONG_AXIS_IN_M4
    )
    expected_M_mid = simply_supported_center_point_load_max_moment(force_in_newton, total_length_in_meter)

    assert_close(fers_dy_mid, expected_dy_mid, abs_tol=TOL.absolute_displacement_in_meter)
    assert_close(abs(fers_mz_member_mid), expected_M_mid, abs_tol=TOL.absolute_moment_in_newton_meter)
    assert_close(abs(fers_mz_left), 0.0, abs_tol=TOL.absolute_moment_in_newton_meter)
    assert_close(abs(fers_mz_right), 0.0, abs_tol=TOL.absolute_moment_in_newton_meter)


# 012_Simply_Supported_with_Intermediate_Load ---------------------------------


def test_012_Simply_Supported_with_Intermediate_Load():
    steel = build_steel_s235()
    section = build_ipe180(steel)

    total_length_in_meter = 6.0
    load_position_from_left_in_meter = 2.0
    force_in_newton = 1000.0

    calculation = FERS()
    n_left = Node(0.0, 0.0, 0.0)
    n_load = Node(load_position_from_left_in_meter, 0.0, 0.0)
    n_right = Node(total_length_in_meter, 0.0, 0.0)

    simple_support = NodalSupport(
        rotation_conditions={
            "X": SupportCondition.fixed(),
            "Y": SupportCondition.free(),
            "Z": SupportCondition.free(),
        }
    )
    n_left.nodal_support = simple_support
    n_right.nodal_support = simple_support

    m1 = Member(start_node=n_left, end_node=n_load, section=section)
    m2 = Member(start_node=n_load, end_node=n_right, section=section)
    calculation.add_member_set(MemberSet(members=[m1, m2]))

    lc = calculation.create_load_case(name="Intermediate Load")
    NodalLoad(node=n_load, load_case=lc, magnitude=force_in_newton, direction=(0.0, -1.0, 0.0))

    calculation.run_analysis()
    res = calculation.results.loadcases["Intermediate Load"]

    fers_mz_left = res.reaction_nodes["1"].nodal_forces.mz
    fers_mz_member_at_load = res.member_results["1"].end_node_forces.mz

    reaction_left_in_newton, reaction_right_in_newton = simply_supported_reactions_for_point_load_at_x(
        force_in_newton, total_length_in_meter, load_position_from_left_in_meter
    )
    expected_moment_under_load = (
        reaction_left_in_newton * load_position_from_left_in_meter
    )  # equals F * a * (L-a)/L

    assert_close(
        abs(fers_mz_member_at_load), expected_moment_under_load, abs_tol=TOL.absolute_moment_in_newton_meter
    )
    assert_close(abs(fers_mz_left), 0.0, abs_tol=TOL.absolute_moment_in_newton_meter)


# 013_Simply_Supported_with_Double_symmetric_Load -----------------------------


def test_013_Simply_Supported_with_Double_symmetric_Load():
    steel = build_steel_s235()
    section = build_ipe180(steel)

    total_length_in_meter = 6.0
    distance_from_support_in_meter = 2.0
    force_per_point_in_newton = 1000.0

    calculation = FERS()
    n_left = Node(0.0, 0.0, 0.0)
    n_a = Node(distance_from_support_in_meter, 0.0, 0.0)
    n_b = Node(total_length_in_meter - distance_from_support_in_meter, 0.0, 0.0)
    n_right = Node(total_length_in_meter, 0.0, 0.0)

    simple_support = NodalSupport(
        rotation_conditions={
            "X": SupportCondition.fixed(),
            "Y": SupportCondition.free(),
            "Z": SupportCondition.free(),
        }
    )
    n_left.nodal_support = simple_support
    n_right.nodal_support = simple_support

    m1 = Member(start_node=n_left, end_node=n_a, section=section)
    m2 = Member(start_node=n_a, end_node=n_b, section=section)
    m3 = Member(start_node=n_b, end_node=n_right, section=section)
    calculation.add_member_set(MemberSet(members=[m1, m2, m3]))

    lc = calculation.create_load_case(name="Double symmetric Load")
    NodalLoad(node=n_a, load_case=lc, magnitude=force_per_point_in_newton, direction=(0.0, -1.0, 0.0))
    NodalLoad(node=n_b, load_case=lc, magnitude=force_per_point_in_newton, direction=(0.0, -1.0, 0.0))

    calculation.run_analysis()
    res = calculation.results.loadcases["Double symmetric Load"]

    fers_mz_member_mid = res.member_results["1"].end_node_forces.mz  # under the left load toward midspan
    expected_mid_moment = simply_supported_symmetric_double_load_mid_moment(
        force_per_point_in_newton, distance_from_support_in_meter
    )
    assert_close(abs(fers_mz_member_mid), expected_mid_moment, abs_tol=TOL.absolute_moment_in_newton_meter)
