from __future__ import annotations
from enum import Enum
from typing import Optional


class SupportConditionType(Enum):
    FIXED = "Fixed"
    FREE = "Free"
    SPRING = "Spring"
    POSITIVE_ONLY = "Positive-only"
    NEGATIVE_ONLY = "Negative-only"


class SupportCondition:
    """
    A single-degree-of-freedom condition for a node support axis:
    - FIXED: exact Dirichlet constraint (handled on the Rust side as a constraint/elimination)
    - FREE: no resistance
    - SPRING: linear spring with 'stiffness' (force/disp for translations, moment/rad for rotations)
    - POSITIVE_ONLY / NEGATIVE_ONLY: unilateral (contact-like). Stiffness is optional:
        * If provided, acts as a spring active only in the allowed direction.
        * If omitted, treat as an ideal unilateral constraint (handled iteratively on the Rust side).
    """

    def __init__(
        self,
        condition_type: SupportConditionType,
        stiffness: Optional[float] = None,
    ):
        self.condition_type = condition_type
        self.stiffness = stiffness
        self._validate()

    def _validate(self) -> None:
        if self.condition_type == SupportConditionType.SPRING:
            if self.stiffness is None:
                raise ValueError("SPRING requires a positive stiffness value.")
            if self.stiffness <= 0.0:
                raise ValueError("SPRING stiffness must be positive.")
        else:
            if self.condition_type in (
                SupportConditionType.POSITIVE_ONLY,
                SupportConditionType.NEGATIVE_ONLY,
            ):
                if self.stiffness is not None and self.stiffness <= 0.0:
                    raise ValueError("Unilateral stiffness, if provided, must be positive.")
            else:
                if self.stiffness is not None:
                    raise ValueError(f"{self.condition_type.value} must not specify stiffness.")

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

    def to_dict(self) -> dict:
        """
        {
          "condition_type": "Fixed" | "Free" | "Spring" | "Positive-only" | "Negative-only",
          "stiffness": number | null
        }
        """
        return {
            "condition_type": self.condition_type.value,
            "stiffness": self.stiffness,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SupportCondition":
        if data is None:
            raise ValueError("SupportCondition.from_dict: 'data' must not be None.")

        # Accept either "condition_type" or "type" as key
        raw_type = (
            data.get("condition_type") or data.get("type") or data.get("ConditionType") or data.get("Type")
        )
        if raw_type is None:
            raise ValueError("SupportCondition.from_dict: missing 'condition_type'/'type' field.")

        stiffness = data.get("stiffness", None)

        # If already an enum, keep it
        if isinstance(raw_type, SupportConditionType):
            condition_type = raw_type
        else:
            # Normalize string variants
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
            else:
                raise ValueError(f"SupportCondition.from_dict: unknown condition_type '{raw_type}'.")

        # Let __init__ + _validate handle correctness
        return cls(condition_type=condition_type, stiffness=stiffness)

    def to_display_string(self) -> str:
        if self.condition_type == SupportConditionType.SPRING:
            return f"Spring (stiffness={self.stiffness})"
        return self.condition_type.value

    def __repr__(self) -> str:
        return f"SupportCondition(type={self.condition_type.value}, stiffness={self.stiffness})"
