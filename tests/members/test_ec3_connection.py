"""EN 1993-1-3 §8.3 bolted connections in thin sheet.

Every expected number is worked by hand in the docstring it sits in, so a
regression has to be argued against the clause rather than against a stored run.
"""

import math

import pytest

from fers_core.members.ec3_connection import (
    GAMMA_M2,
    BoltedLap,
    bearing_resistance,
    bolt_shear_resistance,
    connection_resistance,
    detailing_warnings,
    eccentric_compression_capacity,
    net_section_resistance,
)

FU_S390 = 460.0e6  # ultimate strength of S390GD sheet


def lap(**kw):
    base = dict(d=0.012, t=0.003, f_u=FU_S390, e1=0.036, e2=0.025)
    base.update(kw)
    return BoltedLap(**base)


# ── bearing ────────────────────────────────────────────────────────────────


def test_bearing_at_full_end_distance():
    """M12 through 3 mm of f_u = 460 MPa sheet, e1 = 3d so alpha_b = 1,
    t > 1.25 mm so k_t = 1:

        F_b,Rd = 2.5 * 1 * 1 * 460e6 * 0.012 * 0.003 / 1.25 = 33 120 N
    """
    assert bearing_resistance(lap()) == pytest.approx(33_120.0, rel=1e-9)


def test_a_short_end_distance_cuts_bearing_in_proportion():
    """alpha_b = e1/(3d) = 25/36 = 0.69444, so 33 120 * 0.69444 = 23 000 N."""
    assert bearing_resistance(lap(e1=0.025)) == pytest.approx(23_000.0, rel=1e-6)


def test_alpha_b_never_exceeds_one():
    """Past e1 = 3d the term is capped, so a longer end distance buys nothing."""
    assert bearing_resistance(lap(e1=0.200)) == pytest.approx(bearing_resistance(lap()))


def test_k_t_relieves_only_the_thinnest_sheet():
    """At t = 1.0 mm, k_t = (0.8*1.0 + 1.5)/2.5 = 0.92:

        F_b,Rd = 2.5 * 1 * 0.92 * 460e6 * 0.012 * 0.001 / 1.25 = 10 156.8 N

    and at t = 1.5 mm k_t is back to 1, so the resistance is linear in t again.
    """
    assert bearing_resistance(lap(t=0.001)) == pytest.approx(10_156.8, rel=1e-9)
    assert bearing_resistance(lap(t=0.0015)) == pytest.approx(
        1.5 * bearing_resistance(lap(t=0.001)) / 0.92, rel=1e-9
    )


def test_bearing_adds_up_over_the_bolts():
    assert bearing_resistance(lap(n_bolts=3)) == pytest.approx(3.0 * bearing_resistance(lap()))


# ── bolt shear ─────────────────────────────────────────────────────────────


def test_bolt_shear_through_the_threads():
    """M12 8.8, A_s = 84.3 mm2, alpha_v = 0.6:

    F_v,Rd = 0.6 * 800e6 * 84.3e-6 / 1.25 = 32 371.2 N
    """
    assert bolt_shear_resistance(lap()) == pytest.approx(32_371.2, rel=1e-9)


def test_bolt_shear_through_the_shank_uses_the_gross_area():
    """A = pi/4 * 12^2 = 113.10 mm2, and alpha_v stays 0.6."""
    expected = 0.6 * 800.0e6 * (0.25 * math.pi * 0.012**2) / GAMMA_M2
    assert bolt_shear_resistance(lap(threads_in_shear_plane=False)) == pytest.approx(expected)


def test_the_high_strength_grades_drop_alpha_v():
    """10.9 is stronger but alpha_v falls to 0.5 with the threads in the plane:

    0.5 * 1000e6 * 84.3e-6 / 1.25 = 33 720 N
    """
    assert bolt_shear_resistance(lap(grade="10.9")) == pytest.approx(33_720.0, rel=1e-9)


def test_two_shear_planes_double_it():
    assert bolt_shear_resistance(lap(shear_planes=2)) == pytest.approx(2.0 * bolt_shear_resistance(lap()))


def test_an_untabulated_bolt_in_the_threads_is_refused_not_guessed():
    with pytest.raises(ValueError, match="no tabulated stress area"):
        bolt_shear_resistance(lap(d=0.013))
    # ... but the shank area is geometry, so that path still works
    assert bolt_shear_resistance(lap(d=0.013, threads_in_shear_plane=False)) > 0.0


# ── net section ────────────────────────────────────────────────────────────


def test_net_section_with_the_spread_penalty():
    """A_gross = 525.9 mm2, one M12 in a 13 mm hole through 3 mm:

    A_net = 525.9 - 13*3          = 486.9 mm2
    u     = 2 e2 = 50 mm
    factor= 1 + 3*1*(13/50 - 0.3) = 0.88
    F_n,Rd= 0.88 * 486.9e-6 * 460e6 / 1.25 = 157 678 N
    """
    got = net_section_resistance(lap(e2=0.025), a_gross=525.9e-6)
    assert got == pytest.approx(157_678.0, rel=1e-4)


def test_the_spread_enhancement_is_clamped_at_one():
    """u = 40 mm gives 1 + 3*(0.325 - 0.3) = 1.075, which must not be taken."""
    got = net_section_resistance(lap(e2=0.020), a_gross=525.9e-6)
    a_net = 525.9e-6 - 0.013 * 0.003
    assert got == pytest.approx(a_net * FU_S390 / GAMMA_M2, rel=1e-9)


def test_p2_caps_u():
    wide = net_section_resistance(lap(e2=0.025), a_gross=525.9e-6)
    capped = net_section_resistance(lap(e2=0.025, p2=0.030), a_gross=525.9e-6)
    # u drops from 50 to 30 mm, so d_0/u rises and the factor with it
    assert capped > wide


def test_holes_that_eat_the_section_are_refused():
    with pytest.raises(ValueError, match="remove the whole section"):
        net_section_resistance(lap(n_bolts=20, n_at_section=20), a_gross=525.9e-6)


# ── the envelope ───────────────────────────────────────────────────────────


def test_compression_takes_no_net_section_deduction():
    """The bolt fills the hole (EN 1993-1-1 §6.2.4(1)), so the compression
    envelope is bearing against bolt shear and nothing else."""
    r = connection_resistance(lap(), sense="compression")
    assert r.net_section is None
    assert r.value == pytest.approx(min(r.bearing, r.bolt_shear))
    assert r.governing.startswith("bolt shear")  # 32.4 kN beats 33.1 kN bearing


def test_a_short_end_distance_flips_the_governing_rule():
    r = connection_resistance(lap(e1=0.025), sense="compression")
    assert r.governing.startswith("bearing")
    assert r.value == pytest.approx(23_000.0, rel=1e-6)


def test_tension_brings_the_net_section_in_and_needs_the_area():
    with pytest.raises(ValueError, match="a_gross is required"):
        connection_resistance(lap(), sense="tension")
    r = connection_resistance(lap(), a_gross=525.9e-6, sense="tension")
    assert r.net_section is not None
    assert r.value == pytest.approx(min(r.bearing, r.bolt_shear, r.net_section))


def test_an_unknown_sense_is_refused():
    with pytest.raises(ValueError, match="sense must be"):
        connection_resistance(lap(), sense="shear")


# ── detailing ──────────────────────────────────────────────────────────────


def test_short_distances_are_reported_not_raised():
    """The arithmetic still runs; what it stops being is applicable."""
    warns = detailing_warnings(lap(e1=0.010, e2=0.010))
    assert any("e1" in w for w in warns)
    assert any("e2" in w for w in warns)


def test_the_ductility_rule_fires_when_the_bolt_is_the_weak_part():
    """A 4.6 bolt in a thick sheet shears before the sheet bears out, which is
    what §8.3(5) exists to catch."""
    weak = lap(grade="4.6", t=0.006, e1=0.050)
    assert bolt_shear_resistance(weak) < 1.2 * bearing_resistance(weak)
    assert any("8.3(5)" in w for w in detailing_warnings(weak))
    # and the sound detail does not raise it
    assert not any("8.3(5)" in w for w in detailing_warnings(lap(e1=0.025)))


def test_nonsense_geometry_is_refused_at_construction():
    with pytest.raises(ValueError):
        lap(t=0.0)
    with pytest.raises(ValueError):
        lap(n_at_section=2, n_bolts=1)
    with pytest.raises(ValueError, match="unknown bolt grade"):
        lap(grade="12.9")


# ── eccentricity ───────────────────────────────────────────────────────────


def test_a_concentric_load_is_unaffected():
    assert eccentric_compression_capacity(50_000.0, w_eff=1e-6, f_y=390e6, e=0.0) == 50_000.0


def test_the_interaction_solves_the_linear_sum():
    """N/N_b,Rd + N e/M_Rd = 1 at the returned N, by construction."""
    n_b, w, fy, e = 35_000.0, 1928e-9, 390.0e6, 0.010
    n = eccentric_compression_capacity(n_b, w_eff=w, f_y=fy, e=e)
    assert n / n_b + n * e / (w * fy) == pytest.approx(1.0)
    assert n < n_b


def test_a_bigger_eccentricity_always_costs_more():
    n_b, w, fy = 35_000.0, 1928e-9, 390.0e6
    caps = [eccentric_compression_capacity(n_b, w_eff=w, f_y=fy, e=e) for e in (0.002, 0.010, 0.020)]
    assert caps[0] > caps[1] > caps[2]


def test_gamma_m0_scales_the_moment_side_only():
    n_b, w, fy, e = 35_000.0, 1928e-9, 390.0e6, 0.010
    strict = eccentric_compression_capacity(n_b, w_eff=w, f_y=fy, e=e, gamma_m0=1.1)
    plain = eccentric_compression_capacity(n_b, w_eff=w, f_y=fy, e=e)
    assert strict < plain


def test_nonsense_inputs_are_refused():
    with pytest.raises(ValueError):
        eccentric_compression_capacity(0.0, w_eff=1e-6, f_y=390e6, e=0.01)
    with pytest.raises(ValueError):
        eccentric_compression_capacity(1000.0, w_eff=1e-6, f_y=390e6, e=-0.01)
    with pytest.raises(ValueError):
        eccentric_compression_capacity(1000.0, w_eff=0.0, f_y=390e6, e=0.01)
