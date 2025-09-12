from .supportcondition import SupportCondition
from typing import Dict, Optional, Union


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
        displacement_conditions: Optional[Dict[str, Union[SupportCondition, int, float, str]]] = None,
        rotation_conditions: Optional[Dict[str, Union[SupportCondition, int, float, str]]] = None,
    ):
        self.id = id if id is not None else NodalSupport.id
        if id is None:
            NodalSupport.id += 1

        self.classification = classification

        # Defaults to FIXED in all directions if not provided
        if displacement_conditions is None:
            displacement_conditions = {}
        if rotation_conditions is None:
            rotation_conditions = {}

        # Normalize, auto-fill missing directions as FIXED, and type-check
        self.displacement_conditions: Dict[str, SupportCondition] = self._normalize_conditions(
            displacement_conditions
        )
        self.rotation_conditions: Dict[str, SupportCondition] = self._normalize_conditions(
            rotation_conditions
        )

    @classmethod
    def reset_counter(cls) -> None:
        cls.id = 1

    def _normalize_conditions(
        self,
        conditions: Dict[str, Union[SupportCondition, int, float, str]],
    ) -> Dict[str, SupportCondition]:
        """
        Normalize input dict to have all X,Y,Z with SupportCondition.
        Any direction not mentioned is set to FIXED.
        Accepts:
          - SupportCondition instances
          - numeric (int|float) -> spring with that stiffness
          - strings: "Fixed", "Free", "Positive-only", "Negative-only" (case-insensitive)
        """
        # Start with all FIXED
        normalized: Dict[str, SupportCondition] = {d: SupportCondition.fixed() for d in self.DIRECTIONS}

        # Map provided values onto the baseline
        for raw_key, value in conditions.items():
            key = str(raw_key).upper()
            if key not in self.DIRECTIONS:
                # Allow lower-case 'x','y','z'; otherwise reject unknown keys
                if key in {"X", "Y", "Z"}:
                    pass
                else:
                    raise ValueError(f"Unknown direction key '{raw_key}'. Use one of X, Y, Z.")
            normalized[key] = self._coerce_condition(value, direction=key)

        return normalized

    def _coerce_condition(
        self, value: Union[SupportCondition, int, float, str], direction: str
    ) -> SupportCondition:
        if isinstance(value, SupportCondition):
            return value
        if isinstance(value, (int, float)):
            # Convenience: numeric means spring with that stiffness
            return SupportCondition.spring(float(value))
        if isinstance(value, str):
            name = value.strip().lower()
            if name == "spring":
                raise ValueError(
                    f"Direction '{direction}': 'Spring' is ambiguous without stiffness. "
                    f"Use a numeric stiffness or SupportCondition.spring(k)."
                )
            mapping = {
                "fixed": SupportCondition.fixed(),
                "free": SupportCondition.free(),
                "positive-only": SupportCondition.positive_only(),
                "negative-only": SupportCondition.negative_only(),
            }
            if name not in mapping:
                raise ValueError(
                    f"Direction '{direction}': unknown condition string '{value}'. "
                    f"Supported: Fixed, Free, Positive-only, Negative-only, numeric stiffness"
                )
            return mapping[name]
        raise TypeError(f"Unsupported condition type for '{direction}': {type(value)}")

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
