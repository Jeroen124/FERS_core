"""Beam-end connectors given as a moment-rotation diagram, ``M(phi)``.

The form a connector is specified and tested in, per EN 15512. Expressed instead as
stiffness against end force it can only be read exactly at the tabulated points, and
neither connector looseness nor the end-of-range behaviours can be said at all.

These cover the builder: what it accepts, what it refuses, and that a hinge carrying
one round-trips through the solver's JSON contract. The physics is the solver's, and
is covered there.
"""

import pytest

from fers_core import CurveEndBehaviour, MemberHinge, MomentRotationCurve

# The reference connector from the integrator's filing (N*mm).
CURVE_M1 = [[0.000, 0.0], [0.005, 1_500_000.0], [0.015, 2_500_000.0], [0.040, 3_000_000.0]]
# EN 15512 looseness: 2 mrad of free play before the connector takes any moment.
CURVE_LOOSE = [[0.000, 0.0], [0.002, 0.0], [0.007, 1_500_000.0], [0.017, 2_500_000.0]]


def test_defaults_are_symmetric_and_continuous():
    c = MomentRotationCurve(points=CURVE_M1)
    assert c.symmetric is True
    assert c.start is CurveEndBehaviour.CONTINUOUS
    assert c.end is CurveEndBehaviour.CONTINUOUS


def test_looseness_is_just_a_flat_first_segment():
    """The gap needs no special field, which is the point: it is curve data."""
    c = MomentRotationCurve(points=CURVE_LOOSE)
    assert c.points[1] == [0.002, 0.0]


def test_round_trips_through_the_hinge():
    hinge = MemberHinge(
        id=1,
        moment_rotation_my=MomentRotationCurve(points=CURVE_M1, end=CurveEndBehaviour.YIELDING),
    )
    d = hinge.to_dict()
    assert d["moment_rotation_my"]["end"] == "Yielding"
    assert d["moment_rotation_mx"] is None
    assert MemberHinge.from_dict(d).to_dict() == d


def test_rejects_a_softening_branch():
    """A falling branch has no single-valued secant; the ceiling belongs on `end`."""
    with pytest.raises(ValueError, match="must not decrease"):
        MomentRotationCurve(points=[[0.0, 0.0], [0.01, 2.0e6], [0.02, 1.0e6]])


def test_rejects_non_ascending_rotations():
    with pytest.raises(ValueError, match="ascend strictly"):
        MomentRotationCurve(points=[[0.0, 0.0], [0.01, 1.0e6], [0.01, 2.0e6]])


def test_rejects_a_symmetric_curve_that_misses_the_origin():
    with pytest.raises(ValueError, match=r"\[0.0, 0.0\]"):
        MomentRotationCurve(points=[[0.005, 1.0e6], [0.01, 2.0e6]])


@pytest.mark.parametrize("which", ["start", "end"])
def test_accepts_failure(which):
    """Supported from engine 0.2.58, which latches the break instead of re-reading it.

    Both this builder and the solver used to refuse it. Neither does now, so a curve
    carrying it must round-trip unchanged rather than raise.
    """
    curve = MomentRotationCurve(points=CURVE_M1, **{which: CurveEndBehaviour.FAILURE})
    assert getattr(curve, which) is CurveEndBehaviour.FAILURE
    assert curve.to_dict()[which] == "Failure"


def test_accepts_every_end_behaviour():
    for end in CurveEndBehaviour:
        assert MomentRotationCurve(points=CURVE_M1, end=end).end is end
