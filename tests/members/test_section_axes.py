"""Section local axes: which one a shear-centre offset lands on, and whether the
principal-axis angle is the one the solver checks against.

Both of these were silently wrong, and both are unconservative in the direction
that matters — they feed EN 1993-1-1 §6.3.1 and §6.3.1.4.
"""

import math

import pytest

from fers_core import FERS, AnalysisOrder, Material, Member, MemberSet, Node, NodalLoad, NodalSupport
from fers_core.members.section import Section

S235 = Material(name="S235", e_mod=210e9, g_mod=81e9, density=7850, yield_stress=235e6)


def solver_resolves_principal(sec):
    """Replays `Section::principal_axes` from the Rust side (engine 0.2.68): the
    inertias about y' and z' the element is built with.

    Centroidal values with a product of inertia get Mohr's circle, and the stored
    angle picks which principal axis is y': theta for the major one, theta +/- 90
    for the minor. Values that cannot be centroidal (i_yz^2 >= i_y*i_z) are the
    older principal-value form and pass through.
    """
    i_yz = sec.i_yz or 0.0
    avg = (sec.i_y + sec.i_z) / 2.0
    r = math.hypot((sec.i_y - sec.i_z) / 2.0, i_yz)
    if abs(i_yz) <= 1e-9 * max(abs(sec.i_y), abs(sec.i_z)) or r <= 1e-6 * abs(avg):
        return sec.i_y, sec.i_z
    if sec.i_y * sec.i_z <= i_yz * i_yz:
        return sec.i_y, sec.i_z
    theta = math.degrees(0.5 * math.atan2(-2.0 * i_yz, sec.i_y - sec.i_z))
    if sec.principal_axis_angle is None:
        minor = abs(theta) > 45.0
    else:
        offset = (sec.principal_axis_angle - theta + 90.0) % 180.0 - 90.0
        minor = abs(abs(offset) - 90.0) < math.degrees(0.02)
        assert minor or abs(offset) < math.degrees(0.02), "the engine refuses this angle"
    return (avg - r, avg + r) if minor else (avg + r, avg - r)


def test_a_channel_carries_its_shear_centre_offset_on_local_z():
    """i_y = sp.iyy_c and i_z = sp.ixx_c pins FERS local z to the
    sectionproperties x direction, and a channel's offset lies along it."""
    sec = Section.create_u_section("C 80x50x3", S235, h=0.080, b=0.050, t_f=0.003, t_w=0.003, r=0.003)
    assert abs(sec.y_s) < 1e-6, "the offset does not belong on local y"
    assert sec.z_s == pytest.approx(-0.03226, abs=1e-4)
    # ...and local y really is the weak axis for this shape, which is what makes
    # the mapping above the right way round.
    assert sec.i_y < sec.i_z


def test_a_doubly_symmetric_section_has_no_offset_either_way():
    sec = Section.create_ipe_section("IPE300", S235, h=0.300, b=0.150, t_f=0.0107, t_w=0.0071, r=0.015)
    assert abs(sec.y_s) < 1e-6
    assert abs(sec.z_s) < 1e-6


def test_the_principal_angle_is_the_one_the_solver_compares_against():
    """sectionproperties reports phi in DEGREES (-135 for an equal angle) and in
    its own axes. The SDK sends the Mohr angle instead, the one every engine
    reads: before 0.2.68 any other angle, even -135 for the same axis, made the
    solver use the centroidal pair as if it were principal. For an L 100x100x10
    that is 177 cm4 standing in for 73 cm4.
    """
    sec = Section.create_angle_section(
        "L 100x100x10", S235, h=0.100, b=0.100, t=0.010, r_root=0.012, r_toe=0.006
    )
    assert sec.i_yz is not None and abs(sec.i_yz) > 1e-9
    assert sec.principal_axis_angle == pytest.approx(45.0, abs=1e-6)

    i_max, i_min = solver_resolves_principal(sec)
    # sectionproperties' own principal values for this profile.
    assert i_max * 1e8 == pytest.approx(280.2, abs=0.5)
    assert i_min * 1e8 == pytest.approx(73.0, abs=0.5)
    # The weak principal value is well under the centroidal one — that gap is
    # the whole point, and it is the unconservative direction if missed.
    assert i_min < 0.45 * sec.i_z


def test_a_symmetric_section_reports_no_product_of_inertia():
    sec = Section.create_rhs("RHS 200x100x8", S235, h=0.200, b=0.100, t=0.008)
    assert sec.i_yz is None
    assert sec.principal_axis_angle is None
    # Nothing to rotate, so the stored pair passes through untouched.
    assert solver_resolves_principal(sec) == (sec.i_y, sec.i_z)


def test_either_principal_axis_solves_the_same_section():
    """Engine 0.2.68 reads i_y/i_z/i_yz the same whichever principal axis the angle
    names, or with none, and refuses an angle that names neither. A 1 m cantilever
    with an unsymmetric section and a tip load along local y deflects by
    L^3/(3E) * A^-1 * F, with A the centroidal tensor [[i_z, i_yz], [i_yz, i_y]]."""
    i_y, i_z, i_yz = 658254.7886e-12, 753898.4249e-12, -610365.0e-12
    theta = math.degrees(0.5 * math.atan2(-2.0 * i_yz, i_y - i_z))

    def tip(angle):
        model = FERS()
        model.settings.analysis_options.order = AnalysisOrder.LINEAR
        section = Section(
            name="rail",
            material=S235,
            i_y=i_y,
            i_z=i_z,
            j=634.4e-12,
            area=478.6e-6,
            i_yz=i_yz,
            principal_axis_angle=angle,
        )
        root, end = Node(0.0, 0.0, 0.0), Node(1.0, 0.0, 0.0)
        root.nodal_support = NodalSupport()
        model.add_member_set(MemberSet(members=[Member(start_node=root, end_node=end, section=section)]))
        case = model.create_load_case(name="tip")
        NodalLoad(node=end, load_case=case, magnitude=1000.0, direction=(0, 1, 0))
        model.run_analysis()
        d = model.resultsbundle.loadcases["tip"].displacement_nodes[str(end.id)]
        return d.dy, d.dz

    k = 1000.0 / (3.0 * 210e9 * (i_y * i_z - i_yz**2))
    for angle in (theta, theta - 90.0, theta + 180.0, None):
        assert tip(angle) == pytest.approx((k * i_y, -k * i_yz), rel=1e-6), angle
    with pytest.raises(RuntimeError, match="names neither principal axis"):
        tip(theta + 30.0)


def test_a_turned_section_sends_principal_moduli_and_keeps_the_leg_axis_ones():
    """Engine 0.2.68 bends a section with a product of inertia about its principal
    axes and reads its moduli and shear areas as principal-axis values. The SDK
    sends theta, so y' is sectionproperties' major 11 axis; A_s11 is the shear area
    along it, which the engine's a_sz carries. The leg-axis values stay on
    `geometric` for tools that bend the section in one plane."""
    from sectionproperties.analysis import Section as SPSection
    from sectionproperties.pre.library import angle_section

    sec = Section.create_angle_section(
        "L 100x65x7", S235, h=0.100, b=0.065, t=0.007, r_root=0.010, r_toe=0.005
    )

    geometry = angle_section(d=0.100, b=0.065, t=0.007, r_r=0.010, r_t=0.005, n_r=16)
    geometry.create_mesh(mesh_sizes=[0.100 / 1000.0])
    sp = SPSection(geometry, time_info=False)
    sp.calculate_geometric_properties()
    sp.calculate_warping_properties()
    sp.calculate_plastic_properties()
    z11p, z11m, z22p, z22m = sp.get_zp()
    s11, s22 = sp.get_sp()
    as11, as22 = sp.get_as_p()
    zxxp, zxxm, zyyp, zyym = sp.get_z()
    sxx, syy = sp.get_s()
    asx, asy = sp.get_as()

    assert sec.wel_y == pytest.approx(min(abs(z11p), abs(z11m)), rel=1e-9)
    assert sec.wel_z == pytest.approx(min(abs(z22p), abs(z22m)), rel=1e-9)
    assert (sec.wpl_y, sec.wpl_z) == pytest.approx((s11, s22), rel=1e-9)
    assert (sec.a_sz, sec.a_sy) == pytest.approx((as11, as22), rel=1e-9)
    # The leg axes, mapped as for every other section (FERS z is sp's x).
    assert sec.geometric == pytest.approx(
        {
            "wel_y": min(abs(zyyp), abs(zyym)),
            "wel_z": min(abs(zxxp), abs(zxxm)),
            "wpl_y": syy,
            "wpl_z": sxx,
            "a_sy": asx,
            "a_sz": asy,
        },
        rel=1e-9,
    )
    # y' really is the major axis the moduli were taken about.
    i_major, i_minor = solver_resolves_principal(sec)
    assert i_major == pytest.approx(sp.get_ip()[0], rel=1e-9)
    assert i_minor == pytest.approx(sp.get_ip()[1], rel=1e-9)
    assert "geometric" not in sec.to_dict(), "the solver does not take it"


def test_a_section_without_a_product_of_inertia_has_no_geometric_set():
    sec = Section.create_rhs("RHS 200x100x8", S235, h=0.200, b=0.100, t=0.008)
    assert sec.geometric is None
