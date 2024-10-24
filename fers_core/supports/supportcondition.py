from enum import Enum


class SupportConditionType(Enum):
    FIXED = "Fixed"
    FREE = "Free"
    SPRING = "Spring"
    POSITIVE_ONLY = "Positive-only"
    NEGATIVE_ONLY = "Negative-only"


class SupportCondition:
    FIXED = SupportConditionType.FIXED
    FREE = SupportConditionType.FREE
    SPRING = SupportConditionType.SPRING
    POSITIVE_ONLY = SupportConditionType.POSITIVE_ONLY
    NEGATIVE_ONLY = SupportConditionType.NEGATIVE_ONLY

    def __init__(self, condition=None, stiffness=None):
        """
        Initializes a support condition that defines how a structure can move or deform at a support point.
        The condition can be fixed, free, spring, positive-only, or negative-only.

        :param condition: An instance of SupportConditionType indicating the type of support condition.
                          This should be provided for fixed, free, positive-only, or negative-only conditions.
        :param stiffness: A float representing the stiffness in the specified direction. This should only be
                          provided when the condition is SPRING, and must be a positive value.

        Raises:
            ValueError: If an invalid combination of condition and stiffness is provided.
        """
        if condition is not None and not isinstance(condition, SupportConditionType):
            raise ValueError("Invalid condition type")
        if condition is not None and stiffness is not None:
            raise ValueError("Cannot specify both a condition and stiffness.")

        self.condition = condition
        self.stiffness = stiffness if condition is None else None

    def __eq__(self, other):
        if isinstance(other, SupportCondition):
            return self.condition == other.condition and self.stiffness == other.stiffness
        elif isinstance(other, SupportConditionType):
            return self.condition == other
        return NotImplemented
