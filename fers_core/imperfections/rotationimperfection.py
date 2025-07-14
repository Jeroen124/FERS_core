from ..members.memberset import MemberSet


class RotationImperfection:
    _rotation_imperfection_counter = 1

    def __init__(
        self,
        memberset: list[MemberSet],
        magnitude: float,
        axis: tuple,
        axis_only: bool,
        point: tuple = (0, 0, 0),
    ):
        """
        Initialize a rotation imperfection applied to a memberset.

        Args:
            member: The member to which the imperfection is applied.
            load_case: The LoadCase instance this imperfection is associated with.
            magnitude (float): The magnitude of the rotation in degrees.
            axis (tuple): The axis of rotation (e.g., (0, 0, 1) for Z-axis).
            point (tuple): The point around which the rotation occurs.
        """
        self.id = RotationImperfection._rotation_imperfection_counter
        RotationImperfection._rotation_imperfection_counter += 1
        self.memberset = memberset
        self.magnitude = magnitude
        self.axis = axis
        self.axis_only = axis_only
        self.point = point

    def to_dict(self):
        return {
            "id": self.id,
            "memberset": [ms.id for ms in self.memberset],
            "magnitude": self.magnitude,
            "axis": self.axis,
            "axis_only": self.axis_only,
            "point": self.point,
        }
