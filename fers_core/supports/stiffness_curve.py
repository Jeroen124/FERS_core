from __future__ import annotations

from enum import Enum
import warnings
from typing import List, Optional


class ForceComponent(Enum):
    """Force/moment component that a stiffness curve depends on.

    Maps 1:1 to the Rust ``ForceComponent`` enum used by the solver.

    Member-local variants (N, Vy, Vz) are used for member hinges.
    Global-axis aliases (Fx, Fy, Fz) are intended for support stiffness
    curves where forces are in global coordinates.
    """

    # Member-local
    N = "N"
    Vy = "Vy"
    Vz = "Vz"
    Mx = "Mx"
    My = "My"
    Mz = "Mz"

    # Global-axis aliases (same indices as N/Vy/Vz in the solver)
    Fx = "Fx"
    Fy = "Fy"
    Fz = "Fz"


class StiffnessCurveConfig:
    """Configuration for a non-linear stiffness curve.

    The curve describes how a spring stiffness varies as a function of an
    internal-force component (``depends_on``).  The solver linearly
    interpolates between the ``points`` and clamps at the boundaries.

    Args:
        depends_on: The internal-force component the stiffness depends on.
        points: List of ``[force_value, stiffness]`` pairs, sorted by
            ascending ``force_value``.  At least 2 points are required and
            every stiffness value must be ≥ 0.
        signed: When ``True`` the curve is driven by the **signed** force, so
            tension and compression can have different stiffness and ``points``
            may span negative force values.  When ``False`` (the default) the
            curve is driven by ``abs(force)`` and is therefore symmetric --
            which is the historical behaviour, and the only one this class could
            express before.

    Raises:
        ValueError: If any validation constraint is violated.
    """

    def __init__(
        self,
        depends_on: ForceComponent,
        points: List[List[float]],
        signed: bool = False,
    ) -> None:
        self.depends_on = depends_on
        self.points = points
        self.signed = bool(signed)
        self._validate()

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate(self) -> None:
        if len(self.points) < 2:
            raise ValueError("StiffnessCurveConfig requires at least 2 points.")
        for i, pt in enumerate(self.points):
            if len(pt) != 2:
                raise ValueError(f"Point {i} must have exactly 2 values [force_value, stiffness].")
            if pt[1] < 0:
                raise ValueError(f"Point {i}: stiffness must be non-negative, got {pt[1]}.")
        for i in range(1, len(self.points)):
            if self.points[i][0] < self.points[i - 1][0]:
                raise ValueError(
                    f"Points must be sorted by ascending force value. "
                    f"Point {i} ({self.points[i][0]}) < point {i - 1} ({self.points[i - 1][0]})."
                )
        # A symmetric curve is evaluated at abs(force), so points below zero can
        # never be reached. The solver accepts them -- they are inert, not
        # invalid -- and existing documents contain them, so this warns rather
        # than raising: refusing to load a model the engine would happily solve
        # would be the SDK being stricter than the contract.
        if not self.signed and self.points[0][0] < 0:
            warnings.warn(
                f"StiffnessCurveConfig has negative force values (from {self.points[0][0]}) but "
                "signed=False, so the curve is evaluated at abs(force) and those points are "
                "unreachable. Pass signed=True for a genuinely asymmetric curve.",
                UserWarning,
                stacklevel=3,
            )

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialize to a plain dict matching the Rust ``StiffnessCurveConfig`` JSON schema."""
        payload = {
            "depends_on": self.depends_on.value,
            "points": self.points,
        }
        # Omitted when false so a symmetric curve serializes exactly as it
        # always has -- the Rust field is `#[serde(default)]`, and this keeps
        # existing documents and their fixtures byte-identical.
        if self.signed:
            payload["signed"] = True
        return payload

    @classmethod
    def from_dict(cls, data) -> Optional["StiffnessCurveConfig"]:
        """Deserialize from a dict or a legacy plain list of ``[force, stiffness]`` pairs.

        * **dict** (new format): ``{"depends_on": "Vz", "points": [[0, 1e5], ...],
          "signed": false}``
        * **list** (legacy format): ``[[0, 1e5], ...]`` — wrapped with
          ``ForceComponent.Vz`` as default ``depends_on``.
        * **None**: returns ``None``.
        """
        if data is None:
            return None
        # Legacy format: bare list of [force, stiffness] pairs
        if isinstance(data, list):
            return cls(depends_on=ForceComponent.Vz, points=data)
        # New format: dict with depends_on + points
        depends_on = ForceComponent(data["depends_on"])
        points = data["points"]
        return cls(depends_on=depends_on, points=points, signed=bool(data.get("signed", False)))

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return f"StiffnessCurveConfig(depends_on={self.depends_on.value}, points=[{len(self.points)} pts])"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, StiffnessCurveConfig):
            return NotImplemented
        return self.depends_on == other.depends_on and self.points == other.points
