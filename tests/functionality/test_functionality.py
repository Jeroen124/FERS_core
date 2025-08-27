from fers_core import (
    Node,
    Member,
    FERS,
    MemberSet,
    NodalSupport,
    NodalLoad,
)
from tests.common_functions import (
    build_steel_s235,
    build_ipe180,
    TOL,
    assert_close,
    cantilever_end_point_load_deflection_at_free_end,
    cantilever_end_point_load_fixed_end_moment_magnitude,
)

# strong-axis second moment used by your helpers
SECOND_MOMENT_STRONG_AXIS_IN_M4 = 10.63e-6


def test_041_rigid_member_end_load():
    steel = build_steel_s235()
    section = build_ipe180(steel)

    L_el = 5.0  # elastic span length (m)
    L_rigid = 5.0  # rigid link length (m)
    F = 1000.0  # N (downward)
    r_x = L_rigid  # vector from node 2 -> node 3 along +X

    calc = FERS()

    n1 = Node(0.0, 0.0, 0.0)  # fixed
    n2 = Node(L_el, 0.0, 0.0)  # end of elastic
    n3 = Node(L_el + L_rigid, 0.0, 0.0)  # end of rigid link
    n1.nodal_support = NodalSupport()  # fully fixed

    m_elastic = Member(start_node=n1, end_node=n2, section=section)
    m_rigid = Member(start_node=n2, end_node=n3, member_type="RIGID")
    calc.add_member_set(MemberSet(members=[m_elastic, m_rigid]))

    lc = calc.create_load_case(name="End Load")
    NodalLoad(node=n2, load_case=lc, magnitude=F, direction=(0.0, -1.0, 0.0))

    calc.run_analysis()
    res = calc.results.loadcases["End Load"]

    # --- FERS results
    dy_2 = res.displacement_nodes["2"].dy
    dy_3 = res.displacement_nodes["3"].dy
    rz_2 = res.displacement_nodes["2"].rz
    rz_3 = res.displacement_nodes["3"].rz
    mz_1 = res.reaction_nodes["1"].nodal_forces.mz

    # --- Analytical expectations (cantilever with end load at x = L_el)
    dy_expected = cantilever_end_point_load_deflection_at_free_end(
        F, L_el, steel.e_mod, SECOND_MOMENT_STRONG_AXIS_IN_M4
    )
    mz_expected = cantilever_end_point_load_fixed_end_moment_magnitude(F, L_el)
    rz_expected = -F * L_el**2 / (2.0 * steel.e_mod * SECOND_MOMENT_STRONG_AXIS_IN_M4)

    # 1) End deflection at the elastic tip (node 2)
    assert_close(dy_2, dy_expected, abs_tol=TOL.absolute_displacement_in_meter)

    # 2) Fixed-end reaction moment magnitude
    assert_close(abs(mz_1), mz_expected, abs_tol=TOL.absolute_moment_in_newton_meter)

    # 3) Rigid-link kinematics:
    #    - rotations equal
    rot_tol = getattr(TOL, "absolute_rotation_in_radian", 1e-9)
    assert abs(rz_2 - rz_3) < rot_tol
    #    - analytical rotation at node 2
    assert abs(rz_2 - rz_expected) < rot_tol
    #    - translation mapping: u3 = u2 + (θ × r); with r=(r_x,0,0) -> dy3 = dy2 + rz * r_x
    assert_close(dy_3, dy_2 + rz_2 * r_x, abs_tol=TOL.absolute_displacement_in_meter)
