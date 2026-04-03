from __future__ import annotations

from enum import Enum
from typing import List, Optional

from .stiffness_curve import ForceComponent, StiffnessCurveConfig


class SupportConditionType(Enum):
    FIXED = "Fixed"
    FREE = "Free"
    SPRING = "Spring"
    POSITIVE_ONLY = "Positive-only"
    NEGATIVE_ONLY = "Negative-only"


class SupportCondition:
    """A single-degree-of-freedom condition for a node support axis.

    Condition types
    ---------------
    - **FIXED** — exact Dirichlet constraint (handled on the Rust side as a
      constraint / elimination).
    - **FREE** — no resistance.
    - **SPRING** — linear spring with constant ``stiffness`` (force/disp for
      translations, moment/rad for rotations).  When a ``stiffness_curve`` is
      also provided the curve overrides the constant value and the solver
      re-evaluates the stiffness each iteration based on the specified
      internal-force component (``depends_on``).
    - **POSITIVE_ONLY / NEGATIVE_ONLY** — unilateral (contact-like).  Stiffness
      is optional: if provided it acts as a spring active only in the allowed
      direction; if omitted the Rust side treats it as an ideal unilateral
      constraint.
    """

    def __init__(
        self,
        condition_type: SupportConditionType,
        stiffness: Optional[float] = None,
        stiffness_curve: Optional[StiffnessCurveConfig] = None,
    ) -> None:
        self.condition_type = condition_type
        self.stiffness = stiffness
        self.stiffness_curve = stiffness_curve
        self._validate()

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate(self) -> None:
        if self.condition_type == SupportConditionType.SPRING:
            if self.stiffness_curve is not None:
                # Spring with a stiffness curve — constant stiffness is optional
                # (the curve overrides it).  The curve validates itself in its
                # own __init__.
                pass
            elif self.stiffness is None:
                raise ValueError("SPRING requires a positive stiffness value or a stiffness_curve.")
            elif self.stiffness <= 0.0:
                raise ValueError("SPRING stiffness must be positive.")
        else:
            if self.stiffness_curve is not None:
                raise ValueError(
                    f"{self.condition_type.value} must not specify stiffness_curve "
                    f"(only SPRING supports it)."
                )
            if self.condition_type in (
                SupportConditionType.POSITIVE_ONLY,
                SupportConditionType.NEGATIVE_ONLY,
            ):
                if self.stiffness is not None and self.stiffness <= 0.0:
                    raise ValueError("Unilateral stiffness, if provided, must be positive.")
            else:
                if self.stiffness is not None:
                    raise ValueError(f"{self.condition_type.value} must not specify stiffness.")

    # ------------------------------------------------------------------
    # Factory helpers
    # ------------------------------------------------------------------

    @classmethod
    def fixed(cls) -> "SupportCondition":
        return cls(SupportConditionType.FIXED)

    @classmethod
    def free(cls) -> "SupportCondition":
        return cls(SupportConditionType.FREE)

    @classmethod
    def spring(cls, stiffness: float) -> "SupportCondition":
        return cls(SupportConditionType.SPRING, stiffness=stiffness)

    @classmethod
    def positive_only(cls, stiffness: Optional[float] = None) -> "SupportCondition":
        return cls(SupportConditionType.POSITIVE_ONLY, stiffness=stiffness)

    @classmethod
    def negative_only(cls, stiffness: Optional[float] = None) -> "SupportCondition":
        return cls(SupportConditionType.NEGATIVE_ONLY, stiffness=stiffness)

    @classmethod
    def spring_curve(
        cls,
        depends_on: ForceComponent,
        points: List[List[float]],
    ) -> "SupportCondition":
        """Create a Spring condition whose stiffness varies with an internal-force component.

        Args:
            depends_on: The internal-force component (e.g. ``ForceComponent.Vz``)
                that the stiffness depends on.
            points: List of ``[force_value, stiffness]`` pairs, sorted by
                ascending ``force_value``.  At least 2 points required.
        """
        curve = StiffnessCurveConfig(depends_on=depends_on, points=points)
        return cls(SupportConditionType.SPRING, stiffness_curve=curve)

    @classmethod
    def stiffness_curve(cls, curve_points: List[List[float]]) -> "SupportCondition":
        """Convenience factory — equivalent to ``spring_curve(ForceComponent.Vz, curve_points)``.

        Kept for ergonomic backward compatibility.  Defaults ``depends_on`` to
        ``ForceComponent.Vz`` (axial load).

        Args:
            curve_points: List of ``[force_value, stiffness]`` pairs, sorted by
                ascending ``force_value``.  At least 2 points required.
        """
        return cls.spring_curve(ForceComponent.Vz, curve_points)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialize to a plain dict matching the Rust JSON schema.

        Example output::

            {
              "condition_type": "Spring",
              "stiffness": null,
              "stiffness_curve": {"depends_on": "Vz", "points": [[0, 1e5], ...]}
            }
        """
        d: dict = {
            "condition_type": self.condition_type.value,
            "stiffness": self.stiffness,
        }
        if self.stiffness_curve is not None:
            d["stiffness_curve"] = self.stiffness_curve.to_dict()
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "SupportCondition":
        """Deserialize from a dict.

        Handles both the current format and the legacy ``"StiffnessCurve"``
        condition type (mapped to ``SPRING`` with ``ForceComponent.Vz``).
        """
        if data is None:
            raise ValueError("SupportCondition.from_dict: 'data' must not be None.")

        # Accept either "condition_type" or "type" as key
        raw_type = (
            data.get("condition_type") or data.get("type") or data.get("ConditionType") or data.get("Type")
        )
        if raw_type is None:
            raise ValueError("SupportCondition.from_dict: missing 'condition_type'/'type' field.")

        stiffness = data.get("stiffness", None)
        raw_curve = data.get("stiffness_curve", None)

        # Deserialize stiffness_curve — handles dict (new) and list (legacy)
        stiffness_curve = StiffnessCurveConfig.from_dict(raw_curve)

        # Resolve condition_type
        if isinstance(raw_type, SupportConditionType):
            condition_type = raw_type
        else:
            raw = str(raw_type).strip().lower().replace("_", "-")

            if raw in ("fixed",):
                condition_type = SupportConditionType.FIXED
            elif raw in ("free",):
                condition_type = SupportConditionType.FREE
            elif raw in ("spring",):
                condition_type = SupportConditionType.SPRING
            elif raw in ("positive-only", "positiveonly", "pos-only", "pos"):
                condition_type = SupportConditionType.POSITIVE_ONLY
            elif raw in ("negative-only", "negativeonly", "neg-only", "neg"):
                condition_type = SupportConditionType.NEGATIVE_ONLY
            elif raw in ("stiffnesscurve", "stiffness-curve"):
                # Legacy: map old "StiffnessCurve" type to SPRING
                condition_type = SupportConditionType.SPRING
            else:
                raise ValueError(f"SupportCondition.from_dict: unknown condition_type '{raw_type}'.")

        return cls(condition_type=condition_type, stiffness=stiffness, stiffness_curve=stiffness_curve)

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def to_display_string(self) -> str:
        if self.condition_type == SupportConditionType.SPRING:
            if self.stiffness_curve is not None:
                n = len(self.stiffness_curve.points)
                dep = self.stiffness_curve.depends_on.value
                return f"Spring curve ({n} points, depends_on={dep})"
            return f"Spring (stiffness={self.stiffness})"
        return self.condition_type.value

    def __repr__(self) -> str:
        parts = [f"type={self.condition_type.value}"]
        if self.stiffness is not None:
            parts.append(f"stiffness={self.stiffness}")
        if self.stiffness_curve is not None:
            n = len(self.stiffness_curve.points)
            dep = self.stiffness_curve.depends_on.value
            parts.append(f"stiffness_curve=[{n} points, depends_on={dep}]")
        return f"SupportCondition({', '.join(parts)})"
