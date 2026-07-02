"""CI regression tests: FERS vs the applicable NAFEMS standard benchmarks.

These assert the accuracy claims shown on the public NAFEMS validation page stay true
as the solver evolves. They drive the real solver through `calculate_from_json` (the same
entry point the website's WASM uses), so a regression here is a regression on the page.

Scope (what FERS's element library can represent):
  FV2 — pin-ended double cross, in-plane free vibration      (beam-frame modal)
  FV5 — deep simply-supported beam (Timoshenko)              (beam modal: shear+rotary+torsion+axial)
  LE1 — elliptic membrane (plane stress)                     (membrane static, convergence)
  LE6 — skew Morley rhombic plate under pressure             (plate bending, convergence)
  FVP — simply-supported square plate, free vibration        (plate modal mass, engine >= 0.2.43)
Out of scope by construction (no solver support): 3D solid (LE10/11), curved/axisymmetric
shells (LE2/3/4/7/8/9), thermal, transient. (Flat thin-plate free vibration and rigid-link
offset point masses are now supported — see FVP and the offset-mass Rust regression tests.)
"""
import os
import sys

import pytest

_HERE = os.path.dirname(__file__)
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "benchmarks"))

import nafems_harness as H  # noqa: E402
import FV1_build, FV2_build, FV3_build, FV5_build, FV6_build  # noqa: E402, E401
import FVP_build  # noqa: E402
import LE1_build, LE5_build, LE6_build  # noqa: E402, E401


def _match_nearest(freqs, targets):
    used = [False] * len(freqs)
    out = []
    for t in targets:
        k = min((j for j in range(len(freqs)) if not used[j]), key=lambda j: abs(freqs[j] - t))
        used[k] = True
        out.append((t, freqs[k], H.rel_err_pct(freqs[k], t)))
    return out


def test_FV1_pin_ended_cross():
    """FV1 single '+' cross: same four frequencies as FV2, within 0.5%."""
    freqs, _ = H.modal_frequencies(FV1_build.build(), num_modes=FV1_build.NUM_MODES)
    for t, f, err in _match_nearest(freqs, FV1_build.TARGETS):
        assert err < 0.5, f"FV1 target {t} Hz -> {f:.4f} Hz ({err:.3f}%)"


def test_FV3_free_square_frame():
    """FV3 free-free frame (soft-spring grounded): 3 rigid-body modes + 7 elastic within 0.5%."""
    freqs, _ = H.modal_frequencies(FV3_build.build(), num_modes=FV3_build.NUM_MODES)
    elastic = [f for f in freqs if f > 1.0]
    assert len(freqs) - len(elastic) == 3, "FV3 must have exactly 3 in-plane rigid-body modes"
    for t, f, err in _match_nearest(elastic, FV3_build.TARGETS):
        assert err < 0.5, f"FV3 target {t} Hz -> {f:.4f} Hz ({err:.3f}%)"


def test_FV6_circular_ring():
    """FV6 free-free ring (polygonised, soft-spring grounded): 6 rigid-body modes;
    in-plane + out-of-plane flexural n=2,3,4 within 2% of the thin-ring closed form."""
    freqs, _ = H.modal_frequencies(FV6_build.build(), num_modes=FV6_build.NUM_MODES)
    flex = [f for f in freqs if f > 5.0]
    assert len(freqs) - len(flex) == 6, "FV6 must have exactly 6 rigid-body modes"
    for t, f, err in _match_nearest(flex, FV6_build.TARGETS):
        assert err < 2.0, f"FV6 target {t} Hz -> {f:.3f} Hz ({err:.3f}%)"


def test_FV2_pin_ended_double_cross():
    """All four NAFEMS FV2 target frequencies within 0.5%."""
    freqs, _ = H.modal_frequencies(FV2_build.build(), num_modes=FV2_build.NUM_MODES)
    used = [False] * len(freqs)
    for t in FV2_build.TARGETS:
        k = min((j for j in range(len(freqs)) if not used[j]), key=lambda j: abs(freqs[j] - t))
        used[k] = True
        assert H.rel_err_pct(freqs[k], t) < 0.5, f"FV2 target {t} Hz -> {freqs[k]:.4f} Hz"


def test_FV5_deep_timoshenko_beam():
    """FV5: fit the circular radius to f1, then verify all mode families.
    Torsional/extensional (geometry-independent of the fit) must be near-exact;
    higher flexural carry a few % FE dispersion (better than DIANA's published shells)."""
    # Reproduce the radius fit from the builder.
    lo, hi = 0.6, 1.6
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        if FV5_build.flex1(mid) < 42.649:
            lo = mid
        else:
            hi = mid
    R = 0.5 * (lo + hi)
    freqs, _ = H.modal_frequencies(FV5_build.build(R), num_modes=12)

    def nearest(t):
        return min(freqs, key=lambda f: abs(f - t))

    assert H.rel_err_pct(nearest(77.542), 77.542) < 0.5   # torsional 1
    assert H.rel_err_pct(nearest(125.00), 125.00) < 0.5   # extensional
    assert H.rel_err_pct(nearest(233.10), 233.10) < 1.0   # torsional 2
    assert H.rel_err_pct(nearest(42.649), 42.649) < 0.5   # flexural 1 (fit)
    assert H.rel_err_pct(nearest(148.31), 148.31) < 5.0   # flexural 2
    assert H.rel_err_pct(nearest(284.55), 284.55) < 5.0   # flexural 3


def test_FVP_plate_free_vibration():
    """FVP: simply-supported square plate — exercises plate modal mass (engine >= 0.2.43;
    before this, plate DOFs were massless and had no modes). The fundamental f11 matches
    the Navier closed form, converging from above, within 2% at a 20x20 mesh."""
    freqs, _ = H.modal_frequencies(FVP_build.build(20), num_modes=6)
    elastic = [f for f in freqs if f > 1.0]
    assert elastic, "FVP must return plate bending modes (plate modal mass)"
    f11 = FVP_build.f_mn(1, 1)
    live = min(elastic)
    err = H.rel_err_pct(live, f11)
    assert err < 2.0, f"FVP f11 {live:.3f} Hz vs closed form {f11:.3f} Hz ({err:.2f}%)"
    assert live >= f11, "FVP fundamental must converge to the closed form from above"


def _stress_le1(Nth, Ns):
    c, nd = LE1_build.build(Nth, Ns)
    s, _ = LE1_build.sigma_yy_at_D(H.static_results(c), nd, Nth)
    return s


def test_LE1_elliptic_membrane_converges():
    """LE1: membrane stress at D converges toward 92.7 MPa; fine mesh within 4%."""
    coarse = _stress_le1(24, 4)
    fine = _stress_le1(72, 8)
    e_coarse = H.rel_err_pct(coarse, LE1_build.TARGET)
    e_fine = H.rel_err_pct(fine, LE1_build.TARGET)
    assert fine > coarse, "LE1 must converge from below (stress increasing with refinement)"
    assert e_fine < e_coarse, "LE1 error must decrease with refinement"
    assert e_fine < 4.0, f"LE1 fine-mesh sigma_yy(D) error {e_fine:.2f}% >= 4%"


def test_LE5_zsection_warping_beam():
    """LE5: FERS's 7-DOF warping beam reproduces the restrained-warping flange-tip
    stress (σ = bimoment·ω_n/C_w) within 3% of the NAFEMS −108 MPa shell target."""
    c, _ = LE5_build.build(4)
    res = H.static_results(c)
    bw1, bw2 = LE5_build.bw_at_x25(res)
    bw = 0.5 * (abs(bw1) + abs(bw2))
    sigma = bw * LE5_build.OMEGA_TIP / LE5_build.CW
    assert H.rel_err_pct(sigma, abs(LE5_build.TARGET)) < 3.0, f"LE5 warping stress {sigma/1e6:.2f} MPa"


def _stress_le6(N):
    s, _ = LE6_build.principal_sigma1_at_centre(H.static_results(LE6_build.build(N)))
    return s


def test_LE6_skew_plate_converges():
    """LE6: principal stress at centre converges toward 0.802 MPa; 32x32 within 10%."""
    s16, s24, s32 = _stress_le6(16), _stress_le6(24), _stress_le6(32)
    assert s16 < s24 < s32, "LE6 must converge monotonically from below"
    e32 = H.rel_err_pct(s32, LE6_build.TARGET)
    assert e32 < 10.0, f"LE6 32x32 sigma_1(E) error {e32:.2f}% >= 10%"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
