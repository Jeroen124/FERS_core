"""Bending properties of the EN 1993-1-5 effective section.

Every expected value below is derived by hand from the mid-line plate model, so
a change in the implementation has to be argued against arithmetic rather than
against a previous run.
"""

import math

import pytest

from fers_core.members.ec3_section import (
    channel_fibres,
    channel_plates,
    effective_flexural_properties,
    effective_section,
)

H, B, T, R = 0.080, 0.050, 0.003, 0.003
FY = 390.0e6
# Meshed gross properties of C 80x50x3, from sectionproperties via
# Section.create_u_section. Held as constants so this file needs no mesh.
A_GROSS = 525.9e-6
I_Y_GROSS = 133_623e-12
I_Z_GROSS = 551_339e-12
#: True gross centroid, in the plate frame (z = 0 at the web mid-line).
C_GROSS = (0.0, 13.422e-3)


def _channel():
    plates = channel_plates(H, B, T, T, R)
    return plates, effective_section(plates, A_GROSS, FY)


def _flex(centroid_gross=C_GROSS):
    plates, eff = _channel()
    fib_y, fib_z = channel_fibres(H, B, T, T)
    return effective_flexural_properties(
        plates,
        eff,
        i_y_gross=I_Y_GROSS,
        i_z_gross=I_Z_GROSS,
        fibre_y=fib_y,
        fibre_z=fib_z,
        centroid_gross=centroid_gross,
    )


def test_the_spans_still_describe_the_same_segments():
    """`effective_segments` is now derived from `effective_spans`; the midpoints
    and lengths it reports must not have moved."""
    plates, eff = _channel()
    for pl, res in zip(plates, eff.elements):
        spans = pl.effective_spans(res.rho)
        segs = pl.effective_segments(res.rho)
        assert len(spans) == len(segs)
        for (a, b), (mid, length) in zip(spans, segs):
            assert length == pytest.approx(math.dist(a, b))
            assert mid[0] == pytest.approx(0.5 * (a[0] + b[0]))
            assert mid[1] == pytest.approx(0.5 * (a[1] + b[1]))
        assert sum(length for _, length in segs) == pytest.approx(res.rho * pl.c)


def test_weak_axis_reduction_matches_the_hand_calculation():
    """Mid-line model, flats only. Web c = 68 mm at z = 0, area 204 mm2; two
    flanges c = 44 mm running z = 0 -> 44 at y = +-38.5, area 132 mm2 each.

    gross   z_c = 2*132*22 / 468                       = 12.410 mm
            I_y = 204*3^2/12                           =     153
                + 204*12.410^2                         =  31 417
                + 2*(132*44^2/12 + 132*(22-12.410)^2)  =  66 854
                                                       =  98 424 mm4

    class 4 flange: rho = 0.8030, so 35.33 mm stays effective from the
    supported end, area 106.0 mm2 centred at z = 17.67.

    eff     z_c = 2*106*17.665 / 416                   =   9.005 mm
            I_y = 153 + 204*9.005^2                    =  16 696
                + 2*(106*35.33^2/12 + 106*8.660^2)     =  37 964
                                                       =  54 660 mm4

    reduction = 54 660 / 98 424 = 0.5554
    """
    fl = _flex()
    assert fl.reduction_y == pytest.approx(0.5554, abs=5e-4)
    assert fl.i_eff_y == pytest.approx(0.5554 * I_Y_GROSS, rel=1e-3)


def test_strong_axis_reduction_matches_the_hand_calculation():
    """Same model about local z (I_z = integral of y^2 dA), where only the
    flange AREA is lost and its lever arm 38.5 mm does not move.

    gross   I_z = 204*68^2/12 + 2*(132*3^2/12 + 132*38.5^2) = 470 120 mm4
    eff     I_z = 204*68^2/12 + 2*(106*3^2/12 + 106*38.5^2) = 393 004 mm4
    reduction = 0.8360
    """
    fl = _flex()
    assert fl.reduction_z == pytest.approx(0.8360, abs=5e-4)


def test_the_effective_centroid_is_the_true_one_plus_the_shift():
    """The mid-line model is trusted for the shift, not for the position: a
    supplied gross centroid must come back moved by exactly `e_n`, and the
    shift must be toward the web, away from the discounted flange tips."""
    _, eff = _channel()
    fl = _flex()
    assert fl.centroid_gross == C_GROSS
    assert fl.centroid_eff[1] == pytest.approx(C_GROSS[1] + eff.e_n_z)
    assert eff.e_n_z < 0.0
    assert fl.centroid_eff[1] < C_GROSS[1]


def test_it_falls_back_to_the_midline_centroid():
    """Without a true centroid the mid-line one is used, and it should be close
    to the meshed value without being it."""
    fl = _flex(centroid_gross=None)
    assert fl.centroid_gross[1] == pytest.approx(12.410e-3, abs=5e-5)
    assert fl.centroid_gross[1] != C_GROSS[1]


def test_the_modulus_is_taken_to_the_gross_outline():
    """A fibre is a fibre whether or not its element counted toward `a_eff`, so
    `w_eff_y` divides by the distance to the flange tip of the TRUE outline
    (z = b - t_w/2 = 48.5 mm), not to the end of the effective width."""
    fl = _flex()
    lever = 48.5e-3 - fl.centroid_eff[1]
    assert fl.w_eff_y == pytest.approx(fl.i_eff_y / lever, rel=1e-9)
    assert fl.w_eff_z == pytest.approx(fl.i_eff_z / (0.5 * H), rel=1e-9)
    # and it must be well below the gross modulus about the gross centroid
    assert fl.w_eff_y < I_Y_GROSS / (48.5e-3 - C_GROSS[1])


def test_a_section_with_nothing_to_lose_is_not_reduced():
    """Double the thickness and every element is class 1-3: rho = 1 throughout,
    so the effective section IS the gross section."""
    t = 0.006
    plates = channel_plates(H, B, t, t, R)
    eff = effective_section(plates, A_GROSS, FY)
    assert eff.section_class < 4
    fib_y, fib_z = channel_fibres(H, B, t, t)
    fl = effective_flexural_properties(
        plates,
        eff,
        i_y_gross=I_Y_GROSS,
        i_z_gross=I_Z_GROSS,
        fibre_y=fib_y,
        fibre_z=fib_z,
        centroid_gross=C_GROSS,
    )
    assert fl.reduction_y == pytest.approx(1.0)
    assert fl.reduction_z == pytest.approx(1.0)
    assert fl.centroid_eff == pytest.approx(C_GROSS)
