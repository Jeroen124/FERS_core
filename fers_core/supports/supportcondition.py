from enum import Enum


class SupportConditionType(Enum):
    FIXED = "Fixed"
    FREE = "Free"
    SPRING = "Spring"
    POSITIVE_ONLY = "Positive-only"
    NEGATIVE_ONLY = "Negative-only"


class SupportCondition:
    def __init__(self, condition=None, stiffness=None):
        """
        Initializes the support condition. The condition can be fixed, free, or defined by a specific stiffness.

        :param condition: An instance of SupportConditionType or None if a stiffness is provided.
        :param stiffness: A float representing the stiffness in the specified direction. None if condition is fixed or free.
        """
        if condition is not None and not isinstance(condition, SupportConditionType):
            raise ValueError("Invalid condition type")
        if condition is not None and stiffness is not None:
            raise ValueError("Cannot specify both a condition and stiffness.")

        self.condition = condition
        self.stiffness = stiffness if condition is None else None

    def __repr__(self):
        if self.condition:
            return self.condition.value
        else:
            return f"Stiffness: {self.stiffness}"

    def __eq__(self, other):
        if isinstance(other, SupportConditionType):
            return self.condition == other
        return NotImplemented
