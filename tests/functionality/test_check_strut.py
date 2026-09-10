"""Coverage for the check_strut EC3 compression builder (fers_core.builders)."""

import math

import pytest

from fers_core import Material, check_strut
from fers_core.members.section import Section

S390 = Material(name="S390GD", e_mod=210e9, g_mod=81e9, density=7850, yield_stress=390e6)


def brace_section():
    """The cold-formed plain channel this builder was written for."""
    return Section.create_u_section(
        "C 80x50x3",
        S390,
        h=0.080,
        b=0.050,
        t_f=0.003,
        t_w=0.003,
        r=0.003,
        fabrication="cold_formed",
        # Classification depends on the stress state, so it is opt-in. This
        # section is going into a strut.
        classify_for="compression",
    )


def _rows(model):
    res = model.unity_check_results()
    assert res, "expected a unity-check result"
    u = res[0]
    gov = u["governing"] if isinstance(u, dict) else u.governing
    trace = (gov.get("trace") if isinstance(gov, dict) else gov.trace) or []
    out = {}
    for st in trace:
        label = st.get("label") if isinstance(st, dict) else st.label
        out[label] = st
    return u, gov, out


def _f(step, key):
    return step.get(key) if isinstance(step, dict) else getattr(step, key, None)


def test_the_section_arrives_carrying_its_own_ec3_block():
    """Nothing downstream has to know it is class 4 - the factory derived it."""
    sec = brace_section()
    assert sec.ec3["section_class"] == 4
    assert sec.ec3["buckling_curve_y"] == "C"
    assert sec.ec3["buckling_curve_z"] == "C"
    assert sec.ec3["a_eff"] == pytest.approx(473.9e-6, abs=1.0e-6)
    # The shear-centre offset belongs on local z for a channel. y_s is mesh
    # noise (~1e-8 m) against a 32 mm real offset, not a second component.
    assert abs(sec.y_s) < 1e-6
    assert sec.z_s == pytest.approx(-0.03226, abs=1e-4)


def test_a_class_4_strut_is_checked_on_its_effective_area():
    strut = check_strut(1.5, brace_section(), material=S390, axial_load=10_000.0)
    strut.run_analysis()
    _, gov, rows = _rows(strut)

    # N_c,Rd = A_eff * f_y = 473.9 mm2 * 390 MPa = 184.8 kN, not the gross 205.1 kN.
    assert _f(rows["Axial (6.2.3/4)"], "capacity") == pytest.approx(184.8e3, rel=2e-3)
    assert "effective section properties" in (
        (gov.get("message") if isinstance(gov, dict) else gov.message) or ""
    )


def test_torsional_flexural_buckling_governs_a_short_channel():
    """A channel's shear centre is well off its centroid, so 6.3.1.4 is the check
    that decides it until the weak-axis flexural mode overtakes it."""
    short = check_strut(0.6, brace_section(), material=S390, axial_load=10_000.0)
    short.run_analysis()
    _, _, rows = _rows(short)
    assert "Torsional-flexural buckling (6.3.1.4)" in rows
    assert _f(rows["Governing"], "formula") == "Torsional-flexural buckling (6.3.1.4)"

    long = check_strut(2.5, brace_section(), material=S390, axial_load=10_000.0)
    long.run_analysis()
    _, _, rows = _rows(long)
    assert _f(rows["Governing"], "formula") == "Flexural buckling (6.3.1)"


def test_capacity_is_independent_of_the_probe_load():
    """Every sub-check is linear in the axial force when there is no moment, so
    the allowable must not depend on what we happened to push with."""
    sec = brace_section()
    a = check_strut(1.5, sec, material=S390, axial_load=1_000.0)
    a.run_analysis()
    b = check_strut(1.5, sec, material=S390, axial_load=90_000.0)
    b.run_analysis()
    assert a.compression_capacity() == pytest.approx(b.compression_capacity(), rel=1e-9)


def test_capacity_matches_the_closed_form_at_2500_mm():
    """Hand calc, EN 1993-1-1 6.3.1 with curve c (alpha = 0.49):

    N_cr,y   = pi^2 E I_y / L^2, I_y = 133 623 mm4, L = 2.5 m -> 44.3 kN
    lambda   = sqrt(A_eff f_y / N_cr) = sqrt(473.9e-6 * 390e6 / 44.3e3)
    chi      = 1 / (phi + sqrt(phi^2 - lambda^2))
    N_b,Rd   = chi * A_eff * f_y
    """
    sec = brace_section()
    strut = check_strut(2.5, sec, material=S390, axial_load=10_000.0)
    strut.run_analysis()

    n_cr = math.pi**2 * 210e9 * sec.i_y / 2.5**2
    a_eff = sec.ec3["a_eff"]
    lam = math.sqrt(a_eff * 390e6 / n_cr)
    phi = 0.5 * (1.0 + 0.49 * (lam - 0.2) + lam**2)
    chi = 1.0 / (phi + math.sqrt(phi**2 - lam**2))
    expected = chi * a_eff * 390e6

    assert strut.compression_capacity() == pytest.approx(expected, rel=1e-6)


def test_effective_length_factor_reaches_the_check():
    """k = 2 on a 1 m strut has to land on the same answer as a 2 m strut."""
    sec = brace_section()
    scaled = check_strut(1.0, sec, material=S390, axial_load=10_000.0, k_y=2.0, k_z=2.0)
    scaled.run_analysis()
    plain = check_strut(2.0, sec, material=S390, axial_load=10_000.0)
    plain.run_analysis()
    # k_y/k_z act on the flexural row only; without k_t the torsional length is
    # still the member length, so only that row is comparable here.
    _, _, rows_scaled = _rows(scaled)
    _, _, rows_plain = _rows(plain)
    assert _f(rows_scaled["Flexural buckling (6.3.1)"], "capacity") == pytest.approx(
        _f(rows_plain["Flexural buckling (6.3.1)"], "capacity"), rel=1e-9
    )


def test_k_t_carries_the_torsional_length_too():
    """With every length factor at 2, a 1 m strut has to reproduce a 2 m strut
    outright - envelope included, not just the flexural row.

    This is what k_t is for. Scaling k_y and k_z alone leaves 6.3.1.4 forming
    N_cr,T over the un-scaled member length, and on a channel that row is often
    the one that governs, so the envelope came out unconservative with no sign
    that anything had been missed.
    """
    # 0.3 m doubled to 0.6 m, the length the test above pins as 6.3.1.4's own -
    # at 2 m the flexural row governs and k_t would have nothing to move.
    sec = brace_section()
    scaled = check_strut(0.3, sec, material=S390, axial_load=10_000.0, k_y=2.0, k_z=2.0, k_t=2.0)
    scaled.run_analysis()
    plain = check_strut(0.6, sec, material=S390, axial_load=10_000.0)
    plain.run_analysis()
    assert scaled.compression_capacity() == pytest.approx(plain.compression_capacity(), rel=1e-9)
    _, _, rows = _rows(scaled)
    assert _f(rows["Governing"], "formula") == "Torsional-flexural buckling (6.3.1.4)"

    # ... and leaving k_t behind really does read higher, so the assertion above
    # is not passing for want of anything to measure.
    partial = check_strut(0.3, sec, material=S390, axial_load=10_000.0, k_y=2.0, k_z=2.0)
    partial.run_analysis()
    assert partial.compression_capacity() > scaled.compression_capacity()


def test_rejects_nonsense_inputs():
    sec = brace_section()
    with pytest.raises(ValueError):
        check_strut(0.0, sec, material=S390)
    with pytest.raises(ValueError):
        check_strut(1.0, sec, material=S390, axial_load=-5.0)
