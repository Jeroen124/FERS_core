"""Section local axes: which one a shear-centre offset lands on, and whether the
principal-axis angle is the one the solver checks against.

Both of these were silently wrong, and both are unconservative in the direction
that matters — they feed EN 1993-1-1 §6.3.1 and §6.3.1.4.
"""

import math

import pytest

from fers_core import Material
from fers_core.members.section import Section

S235 = Material(name="S235", e_mod=210e9, g_mod=81e9, density=7850, yield_stress=235e6)


def solver_resolves_principal(sec):
    """Replays `Section::principal_bending_inertias` from the Rust side.

    It only converts when the stored angle matches its own Mohr angle within
    ~1°; otherwise it takes i_y/i_z to be principal already and passes them
    straight through.
    """
    if not sec.i_yz or abs(sec.i_yz) <= 1e-12:
        return sec.i_y, sec.i_z
    theta = 0.5 * math.atan2(-2.0 * sec.i_yz, sec.i_y - sec.i_z)
    stored = math.radians(sec.principal_axis_angle or 0.0)
    if abs(theta - stored) >= 0.02:
        return sec.i_y, sec.i_z  # treated as already principal — no rotation
    avg = (sec.i_y + sec.i_z) / 2.0
    r = math.hypot((sec.i_y - sec.i_z) / 2.0, sec.i_yz)
    return avg + r, avg - r


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
    """sectionproperties reports phi in DEGREES (-135 for an equal angle), and
    -135 names the same axis as +45 but fails the solver's comparison — so the
    rotation gets skipped and the centroidal pair is used as if it were
    principal. For an L 100x100x10 that is 177 cm4 standing in for 73 cm4.
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
