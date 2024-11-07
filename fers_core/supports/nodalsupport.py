from .supportcondition import SupportCondition
from typing import Optional


class NodalSupport:
    DIRECTIONS = ["X", "Y", "Z"]
    id = 1

    def __init__(
        self,
        id: Optional[int] = None,
        classification: Optional[str] = None,
        displacement_conditions: Optional[dict] = None,
        rotation_conditions: Optional[dict] = None,
    ):
        """
        Initialize a Nodal Support instance with optional stiffness
        specifications for displacement and rotation.
        Defaults to a fixed condition if no conditions are provided.

        :param id: Primary key for the nodal support instance.
        :param classification: Optional classification for the nodal support.
        :param displacement_conditions: Optional dictionary with conditions per direction.
        :param rotation_conditions: Optional dictionary with conditions per direction.
        """
        # Default condition for all directions
        default_condition = SupportCondition(condition=SupportCondition.FIXED)

        self.id = id or NodalSupport.id
        if id is None:
            NodalSupport.id += 1
        self.classification = classification

        # Initialize conditions; default to fixed if none provided
        self.displacement_conditions = (
            {
                direction: displacement_conditions.get(direction, default_condition)
                for direction in self.DIRECTIONS
            }
            if displacement_conditions
            else self._default_conditions()
        )

        self.rotation_conditions = (
            {
                direction: rotation_conditions.get(direction, default_condition)
                for direction in self.DIRECTIONS
            }
            if rotation_conditions
            else self._default_conditions()
        )

    @classmethod
    def reset_counter(cls):
        """Reset the nodal support counter to 1."""
        cls.id = 1

    def _default_conditions(self) -> dict:
        """Return default fixed conditions for all directions."""
        return {
            direction: SupportCondition(condition=SupportCondition.FIXED) for direction in self.DIRECTIONS
        }

    def __repr__(self) -> str:
        return (
            f"NodalSupport(id={self.id}, type={self.classification}, "
            f"displacement_conditions={self.displacement_conditions}, "
            f"rotation_conditions={self.rotation_conditions})"
        )

    def to_dict(self) -> dict:
        """Convert the nodal support instance to a dictionary with readable conditions."""

        def condition_to_string(condition):
            """Helper to convert a SupportCondition to a readable string."""
            if condition.condition:
                return condition.condition.value  # This gets the readable form, like "Fixed"
            elif condition.stiffness is not None:
                return f"Spring (stiffness={condition.stiffness})"
            return "Custom"

        return {
            "id": self.id,
            "classification": self.classification,
            "displacement_conditions": {
                direction: condition_to_string(cond)
                for direction, cond in self.displacement_conditions.items()
            },
            "rotation_conditions": {
                direction: condition_to_string(cond) for direction, cond in self.rotation_conditions.items()
            },
        }
