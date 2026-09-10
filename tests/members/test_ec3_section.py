"""EN 1993-1-1 classification and EN 1993-1-5 effective areas.

Every expected value here is a hand calculation against the code clauses, not a
capture of what the module happens to return.
"""

import math

import pytest

from fers_core.members.ec3_section import (
    angle_class,
    buckling_curves,
    channel_plates,
    effective_section,
    epsilon,
    i_plates,
    plate_class,
    plate_rho,
    rhs_plates,
    tube_class,
)

# The brace this module was written for: a cold-formed plain channel,
# 80 x 50 x 3, in S390GD. Gross area from a meshed section-properties run.
CHANNEL = dict(h=0.080, b=0.050, t_f=0.003, t_w=0.003, r=0.003)
CHANNEL_A_GROSS = 526.0e-6
S390 = 390.0e6


def test_epsilon_matches_the_definition():
    assert epsilon(235.0e6) == pytest.approx(1.0)
    assert epsilon(355.0e6) == pytest.approx(math.sqrt(235.0 / 355.0), rel=1e-12)
    assert epsilon(S390) == pytest.approx(0.77625, abs=5e-6)
    with pytest.raises(ValueError):
        epsilon(0.0)


def test_table_5_2_limits_at_the_boundaries():
    eps = 1.0  # S235
    # Internal: 33 / 38 / 42
    assert plate_class("internal", 33.0, eps) == 1
    assert plate_class("internal", 33.01, eps) == 2
    assert plate_class("internal", 38.0, eps) == 2
    assert plate_class("internal", 42.0, eps) == 3
    assert plate_class("internal", 42.01, eps) == 4
    # Outstand: 9 / 10 / 14
    assert plate_class("outstand", 9.0, eps) == 1
    assert plate_class("outstand", 10.0, eps) == 2
    assert plate_class("outstand", 14.0, eps) == 3
    assert plate_class("outstand", 14.01, eps) == 4


def test_en_1993_1_5_reduction_factors():
    eps = 1.0
    # Internal, psi = 1: plateau at lambda_p = 0.5 + sqrt(0.03) = 0.6732, which
    # is c/t = 0.6732 * 28.4 * 2 = 38.24.
    rho, lam = plate_rho("internal", 38.0, eps)
    assert lam == pytest.approx(38.0 / (28.4 * 2.0), rel=1e-12)
    assert rho == 1.0
    rho, lam = plate_rho("internal", 60.0, eps)
    assert lam == pytest.approx(60.0 / 56.8, rel=1e-12)
    assert rho == pytest.approx((lam - 0.22) / lam**2, rel=1e-12)

    # Outstand, psi = 1: plateau at lambda_p = 0.748, i.e. c/t = 13.93. Note
    # that this sits just BELOW the class 3 limit of 14 eps, so the raw factor
    # already dips under 1 while the element is still class 3 - which is why
    # effective_section() reduces class 4 elements only.
    rho, _ = plate_rho("outstand", 13.9, eps)
    assert rho == 1.0
    rho, _ = plate_rho("outstand", 14.0, eps)
    assert rho < 1.0
    rho, lam = plate_rho("outstand", 25.0, eps)
    assert lam == pytest.approx(25.0 / (28.4 * math.sqrt(0.43)), rel=1e-12)
    assert rho == pytest.approx((lam - 0.188) / lam**2, rel=1e-12)
    assert rho < 1.0


def test_channel_flat_widths_are_the_notional_flats():
    web, top, bottom = channel_plates(**CHANNEL)
    # web: h - 2*t_f - 2*r ; flange: b - t_w - r
    assert web.c == pytest.approx(0.068)
    assert top.c == pytest.approx(0.044)
    assert bottom.c == pytest.approx(0.044)
    assert web.kind == "internal"
    assert top.kind == "outstand"


def test_channel_80x50x3_s390_is_class_4_on_the_flanges():
    """Hand calc: eps = 0.77625.

    web      c/t = 68/3  = 22.67 <= 33 eps = 25.61          -> class 1, rho = 1
    flange   c/t = 44/3  = 14.67 >  14 eps = 10.87          -> class 4
             lambda_p = 14.667 / (28.4 * 0.77625 * 0.65574) = 1.0146
             rho      = (1.0146 - 0.188) / 1.0146^2         = 0.8030
             b_eff    = 0.8030 * 44                         = 35.3 mm
    A_eff = 526.0 - 2 * (1 - 0.8030) * 44 * 3               = 474.0 mm2
    """
    es = effective_section(channel_plates(**CHANNEL), CHANNEL_A_GROSS, S390)

    web, top, bottom = es.elements
    assert web.section_class == 1
    assert web.rho == 1.0
    for fl in (top, bottom):
        assert fl.section_class == 4
        assert fl.lambda_p == pytest.approx(1.0146, abs=5e-4)
        assert fl.rho == pytest.approx(0.8030, abs=5e-4)
        assert fl.b_eff == pytest.approx(0.0353, abs=5e-5)

    assert es.section_class == 4
    assert es.is_class4
    assert es.a_eff == pytest.approx(474.0e-6, abs=0.5e-6)
    assert es.area_ratio == pytest.approx(0.901, abs=1e-3)


def test_effective_centroid_shifts_toward_the_web():
    """Losing the flange tips pulls the centroid back across the section.

    The channel is symmetric about local z, so nothing moves along y; the flange
    tips both sit on the +z side, so the shift has to be negative.
    """
    es = effective_section(channel_plates(**CHANNEL), CHANNEL_A_GROSS, S390)
    assert es.e_n_y == pytest.approx(0.0, abs=1e-12)
    assert es.e_n_z < 0.0
    assert abs(es.e_n_z) == pytest.approx(0.0034, abs=2e-4)


def test_a_class_1_to_3_element_is_never_reduced():
    """rho dips below 1 just inside the class 3 limit; applying it there would
    double-count the slenderness, so only class 4 elements get reduced."""
    # An outstand at exactly c/t = 14 eps is class 3, yet its raw factor has
    # already left the plateau (which ends at c/t = 13.93).
    eps = epsilon(235.0e6)
    assert plate_class("outstand", 14.0, eps) == 3
    rho_raw, _ = plate_rho("outstand", 14.0, eps)
    assert rho_raw < 1.0, "the raw factor does dip below 1 here"

    # A stocky I-section: everything class 1-3, so A_eff == A_gross exactly.
    plates = i_plates(h=0.300, b=0.150, t_f=0.0107, t_w=0.0071, r=0.015)
    es = effective_section(plates, 53.8e-4, 235.0e6)
    assert es.section_class <= 3
    assert es.a_eff == pytest.approx(53.8e-4, rel=1e-12)
    assert es.e_n_y == pytest.approx(0.0, abs=1e-12)
    assert es.e_n_z == pytest.approx(0.0, abs=1e-12)


def test_rhs_walls_are_all_internal():
    plates = rhs_plates(h=0.100, b=0.050, t=0.005, r_out=0.010)
    assert [p.kind for p in plates] == ["internal"] * 4
    es = effective_section(plates, 13.4e-4, 235.0e6)
    assert es.section_class == 1


def test_tube_and_angle_use_their_own_table_5_2_sheets():
    # CHS: class boundaries at 50 / 70 / 90 eps^2.
    assert tube_class(d=0.1143, t=0.005, f_y=235.0e6) == 1  # d/t = 22.9
    assert tube_class(d=0.1143, t=0.0018, f_y=235.0e6) == 2  # d/t = 63.5
    assert tube_class(d=0.1143, t=0.0014, f_y=235.0e6) == 3  # d/t = 81.6
    assert tube_class(d=0.1143, t=0.001, f_y=235.0e6) == 4  # d/t = 114
    # Angle: both conditions must hold.
    assert angle_class(h=0.100, b=0.100, t=0.010, f_y=235.0e6) == 3  # 10.0 / 10.0
    assert angle_class(h=0.100, b=0.100, t=0.005, f_y=235.0e6) == 4  # 20.0 > 15


def test_buckling_curves_follow_table_6_2():
    # U / channel: curve c about either axis.
    assert buckling_curves("channel", "cold_formed", S390)[:2] == ("c", "c")
    # Hollow: hot-finished a, cold-formed c, a0 for the high-grade row.
    assert buckling_curves("rhs", "hot_finished", 235.0e6)[:2] == ("a", "a")
    assert buckling_curves("rhs", "cold_formed", 235.0e6)[:2] == ("c", "c")
    assert buckling_curves("chs", "hot_finished", 460.0e6)[:2] == ("a0", "a0")
    # Angle: curve b.
    assert buckling_curves("angle", "hot_rolled", 235.0e6)[:2] == ("b", "b")
    # Rolled I, h/b > 1.2 and t_f <= 40: strong axis a, weak axis b. Local z is
    # the strong axis here, so the pair comes back (weak, strong) = (b, a).
    assert buckling_curves("i", "hot_rolled", 235.0e6, h=0.300, b=0.150, t_f=0.0107)[:2] == ("b", "a")
    # Thick-flanged stocky I drops to d/d.
    assert buckling_curves("i", "hot_rolled", 235.0e6, h=0.300, b=0.300, t_f=0.120)[:2] == ("d", "d")
