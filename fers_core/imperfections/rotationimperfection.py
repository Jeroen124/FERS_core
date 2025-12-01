from typing import Any
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
        self.memberset = memberset
        self.magnitude = magnitude
        self.axis = axis
        self.axis_only = axis_only
        self.point = point

    def to_dict(self):
        return {
            "memberset": [ms.id for ms in self.memberset],
            "magnitude": self.magnitude,
            "axis": [self.axis[0], self.axis[1], self.axis[2]],
        }

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        *,
        membersets_by_id: dict[int, MemberSet],
    ) -> "RotationImperfection":
        """
        data schema (expected):
        {
            "memberset": [1, 2],           # or "membersets"
            "magnitude": 0.005,
            "axis": [0, 0, 1],
            "axis_only": true,             # optional
            "point": [0, 0, 0]             # optional
        }
        """

        def _as_list(value, field_name: str):
            if value is None:
                return []
            if isinstance(value, list):
                return value
            raise TypeError(f"Expected '{field_name}' to be a list or null, got {type(value).__name__}")

        # Resolve member sets
        ms_ids = _as_list(
            data.get("memberset") or data.get("membersets"),
            "memberset",
        )
        if not ms_ids:
            raise ValueError("RotationImperfection.from_dict: 'memberset' list is required.")

        membersets: list[MemberSet] = []
        for ms_id in ms_ids:
            ms = membersets_by_id.get(ms_id)
            if ms is None:
                raise KeyError(f"RotationImperfection.from_dict: MemberSet with id={ms_id} not found.")
            membersets.append(ms)

        magnitude = float(data.get("magnitude", 0.0))

        axis_raw = data.get("axis", (0.0, 0.0, 1.0))
        axis = tuple(axis_raw) if isinstance(axis_raw, (list, tuple)) else tuple(float(x) for x in axis_raw)

        axis_only = bool(data.get("axis_only", False))

        point_raw = data.get("point", (0.0, 0.0, 0.0))
        point = (
            tuple(point_raw) if isinstance(point_raw, (list, tuple)) else tuple(float(x) for x in point_raw)
        )

        return cls(
            memberset=membersets,
            magnitude=magnitude,
            axis=axis,
            axis_only=axis_only,
            point=point,
        )
