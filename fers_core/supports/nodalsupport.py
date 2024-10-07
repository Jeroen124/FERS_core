from .supportcondition import SupportCondition
from typing import Optional


class NodalSupport:
    DIRECTIONS = ["X", "Y", "Z"]
    _nodal_support_counter = 1

    def __init__(
        self,
        support_id: Optional[int] = None,
        classification: Optional[str] = None,
        displacement_conditions: Optional[dict] = None,
        rotation_conditions: Optional[dict] = None,
    ):
        """
        Initialize a Nodal Support instance with optional stiffness
        specifications for displacement and rotation.
        Defaults to a fixed condition if no conditions are provided.

        :param support_id: Primary key for the nodal support instance.
        :param classification: Optional classification for the nodal support.
        :param displacement_conditions: Optional dictionary with conditions per direction.
        :param rotation_conditions: Optional dictionary with conditions per direction.
        """
        # Default condition for all directions
        default_condition = SupportCondition(condition=SupportCondition.FIXED)

        self.support_id = support_id or self._get_next_support_id()
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
        cls._nodal_support_counter = 1

    def _get_next_support_id(self) -> int:
        """Generate and return the next primary key."""
        support_id = NodalSupport._nodal_support_counter
        NodalSupport._nodal_support_counter += 1
        return support_id

    def _default_conditions(self) -> dict:
        """Return default fixed conditions for all directions."""
        return {
            direction: SupportCondition(condition=SupportCondition.FIXED) for direction in self.DIRECTIONS
        }

    def __repr__(self) -> str:
        return (
            f"NodalSupport(support_id={self.support_id}, type={self.type}, "
            f"displacement_conditions={self.displacement_conditions}, "
            f"rotation_conditions={self.rotation_conditions})"
        )
