from __future__ import annotations

from enum import Enum
from typing import List, Optional


class CurveEndBehaviour(Enum):
    """What a connector does beyond the end of its tabulated diagram.

    Maps 1:1 to the solver's ``CurveEndBehaviour``, and to the four behaviours
    a member-hinge moment-rotation diagram can specify.
    """

    #: Extrapolate the last segment's slope indefinitely. The default, and what a
    #: curve that simply stops short of its real range usually means.
    CONTINUOUS = "Continuous"
    #: Rotation frozen at the last tabulated point: rigid beyond it.
    STOP = "Stop"
    #: Moment capped at the last tabulated point: the connector yields and rotates on.
    #:
    #: From engine 0.2.59 this redistributes properly on an indeterminate frame:
    #: the connector holds its plateau and the moment it cannot carry appears
    #: elsewhere. Earlier engines could not converge that case at all — the secant
    #: was read at the end moment, which means inverting ``M(phi)`` across a
    #: near-flat plateau, and it oscillated. It is read at the rotation there now.
    #:
    #: On a *determinate* span there is nothing to redistribute into: statics fixes
    #: the connector moment at ``F * lever`` whatever the connector does, so a
    #: demand above the cap has no solution. The solver reports that rather than
    #: returning a very large deflection, and names the connector.
    YIELDING = "Yielding"
    #: The connector fails: no moment transmitted beyond, leaving a free hinge.
    #:
    #: Supported from engine 0.2.58. Failure is irreversible, so the solver latches
    #: the break per member end and per DOF rather than re-reading it from the
    #: current moment -- without that a released connector reads zero moment on the
    #: next iterate, concludes it is intact and re-engages.
    #:
    #: A structure that has no equilibrium without the connector -- a determinate
    #: one never does -- comes back with a ``hinge_connector_failed`` error rather
    #: than a deflection. Use :attr:`YIELDING` for a connector that stops taking
    #: *more* moment but keeps carrying what it has.
    FAILURE = "Failure"


class MomentRotationCurve:
    """A beam-end connector's moment-rotation characteristic, ``M(phi)``.

    The form a connector is actually specified and tested in -- EN 15512 measures
    moment against rotation. :class:`~fers_core.supports.stiffness_curve.StiffnessCurveConfig`
    expresses the same connector as stiffness against end force, ``k(M)``, which the
    solver interpolates linearly in ``M`` while the real characteristic is linear in
    ``phi``; the two agree only at the tabulated points. Prefer this class for a
    connector you have a test curve for.

    Requires ``fers_calculations >= 0.2.57``. Mutually exclusive with the matching
    ``stiffness_curve_m*`` on the same hinge DOF -- the solver rejects a model that
    sets both, rather than picking one.

    Args:
        points: ``[rotation, moment]`` pairs sorted by ascending rotation, at least
            two of them. Rotation is in **radians** in every unit system; moment is
            in the model's units. Moments must not decrease: a softening branch has
            no single-valued secant, and a moment ceiling is expressed with
            ``end=YIELDING`` instead.
        symmetric: Mirror the diagram through the origin so hogging and sagging
            behave identically and ``points`` only has to carry ``phi >= 0``. The
            usual case, and the default.
        start: Behaviour below the first tabulated point. Only reachable on an
            asymmetric diagram.
        end: Behaviour above the last tabulated point.

    Looseness -- EN 15512's free play before the connector takes any moment -- is
    just a flat first segment::

        MomentRotationCurve(points=[[0.0, 0.0], [0.002, 0.0], [0.010, 2.0e6]])

    Raises:
        ValueError: If any validation constraint is violated. The solver validates
            again on its own side; this is here so a mistake surfaces where it was
            made.
    """

    def __init__(
        self,
        points: List[List[float]],
        symmetric: bool = True,
        start: CurveEndBehaviour = CurveEndBehaviour.CONTINUOUS,
        end: CurveEndBehaviour = CurveEndBehaviour.CONTINUOUS,
    ) -> None:
        if points is None or len(points) < 2:
            raise ValueError("MomentRotationCurve needs at least 2 [rotation, moment] points.")
        for i, p in enumerate(points):
            if len(p) != 2:
                raise ValueError(f"MomentRotationCurve point {i} must be [rotation, moment], got {p!r}.")
        for i in range(1, len(points)):
            if points[i][0] <= points[i - 1][0]:
                raise ValueError(
                    f"MomentRotationCurve rotations must ascend strictly "
                    f"(point {i} is {points[i][0]} after {points[i - 1][0]})."
                )
            if points[i][1] < points[i - 1][1]:
                raise ValueError(
                    f"MomentRotationCurve moments must not decrease "
                    f"(point {i} is {points[i][1]} after {points[i - 1][1]}). "
                    f"Express a moment ceiling with end=CurveEndBehaviour.YIELDING."
                )
        if symmetric and (points[0][0] != 0.0 or points[0][1] != 0.0):
            raise ValueError(
                "A symmetric MomentRotationCurve must start at [0.0, 0.0] and tabulate only "
                f"positive rotations (got {points[0]!r}). Pass symmetric=False for a genuinely "
                "asymmetric connector."
            )

        self.points = [[float(a), float(b)] for a, b in points]
        self.symmetric = bool(symmetric)
        self.start = start
        self.end = end

    def to_dict(self) -> dict:
        return {
            "points": self.points,
            "symmetric": self.symmetric,
            "start": self.start.value,
            "end": self.end.value,
        }

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> Optional["MomentRotationCurve"]:
        if not data:
            return None
        return cls(
            points=data["points"],
            symmetric=bool(data.get("symmetric", True)),
            start=CurveEndBehaviour(data.get("start", "Continuous")),
            end=CurveEndBehaviour(data.get("end", "Continuous")),
        )
