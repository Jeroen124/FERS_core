from .supportcondition import SupportCondition
from typing import Dict, Optional


class NodalSupport:
    """
    Per-node support definition in GLOBAL axes.
    Each axis has an independent SupportCondition for translation (X,Y,Z) and rotation (X,Y,Z).
    """

    DIRECTIONS = ["X", "Y", "Z"]
    id = 1

    def __init__(
        self,
        id: Optional[int] = None,
        classification: Optional[str] = None,
        displacement_conditions: Optional[Dict[str, SupportCondition]] = None,
        rotation_conditions: Optional[Dict[str, SupportCondition]] = None,
    ):
        self.id = id if id is not None else NodalSupport.id
        if id is None:
            NodalSupport.id += 1

        self.classification = classification

        # Defaults to FIXED in all directions if not provided
        if displacement_conditions is None:
            displacement_conditions = {d: SupportCondition.fixed() for d in self.DIRECTIONS}
        if rotation_conditions is None:
            rotation_conditions = {d: SupportCondition.fixed() for d in self.DIRECTIONS}

        # Normalize and type-check the dictionaries
        self.displacement_conditions: Dict[str, SupportCondition] = self._normalize_conditions(
            displacement_conditions
        )
        self.rotation_conditions: Dict[str, SupportCondition] = self._normalize_conditions(
            rotation_conditions
        )

    @classmethod
    def reset_counter(cls) -> None:
        cls.id = 1

    def _normalize_conditions(self, conditions: Dict[str, SupportCondition]) -> Dict[str, SupportCondition]:
        normalized: Dict[str, SupportCondition] = {}
        for direction in self.DIRECTIONS:
            if direction not in conditions:
                raise ValueError(f"Missing condition for direction '{direction}'.")
            value = conditions[direction]
            if isinstance(value, SupportCondition):
                normalized[direction] = value
            elif isinstance(value, (int, float)):
                # Convenience: numeric means spring with that stiffness
                normalized[direction] = SupportCondition.spring(float(value))
            elif isinstance(value, str):
                # Convenience: string means simple named condition
                mapping = {
                    "Fixed": SupportCondition.fixed(),
                    "Free": SupportCondition.free(),
                    "Spring": None,  # ambiguous without stiffness; reject
                    "Positive-only": SupportCondition.positive_only(),
                    "Negative-only": SupportCondition.negative_only(),
                }
                if value == "Spring":
                    raise ValueError("Use a numeric stiffness or SupportCondition.spring(k) for a spring.")
                if value not in mapping:
                    raise ValueError(f"Unknown condition string '{value}'.")
                normalized[direction] = mapping[value]
            else:
                raise TypeError(f"Unsupported condition type for '{direction}': {type(value)}")
        return normalized

    def to_exchange_dict(self) -> dict:
        """
        Stable wire format for Rust (JSON). Example:

        {
          "id": 3,
          "classification": "Baseplate SR",
          "displacement_conditions": {
            "X": {"type": "Free",   "stiffness": null},
            "Y": {"type": "Spring", "stiffness": 1.5e7},
            "Z": {"type": "Fixed",  "stiffness": null}
          },
          "rotation_conditions": {
            "X": {"type": "Free",   "stiffness": null},
            "Y": {"type": "Free",   "stiffness": null},
            "Z": {"type": "Spring", "stiffness": 6.0e6}
          }
        }
        """
        return {
            "id": self.id,
            "classification": self.classification,
            "displacement_conditions": {
                direction: condition.to_exchange_dict()
                for direction, condition in self.displacement_conditions.items()
            },
            "rotation_conditions": {
                direction: condition.to_exchange_dict()
                for direction, condition in self.rotation_conditions.items()
            },
        }

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "classification": self.classification,
            "displacement_conditions": {
                direction: condition.to_dict()
                for direction, condition in self.displacement_conditions.items()
            },
            "rotation_conditions": {
                direction: condition.to_dict() for direction, condition in self.rotation_conditions.items()
            },
        }

    def __repr__(self) -> str:
        return (
            f"NodalSupport(id={self.id}, classification={self.classification}, "
            f"displacement_conditions={self.displacement_conditions}, "
            f"rotation_conditions={self.rotation_conditions})"
        )
