from typing import Dict, Any, Optional, Tuple

from fers_core.loads.loadcase import LoadCase
from fers_core.members.member import Member


class MemberPointMoment:
    """
    Represents a concentrated point moment applied along a member at a fractional position.

    Attributes:
        id (int): Unique identifier for the moment.
        member (Member): The member on which the moment is applied.
        load_case (LoadCase): The load case to which this moment belongs.
        magnitude (float): The magnitude of the moment.
        direction (Tuple[float, float, float]): Moment direction unit vector.
        position (float): Fractional position along the member (0.0 = start, 1.0 = end).
        axes (str): Coordinate axes for the direction: "global" or "local".
    """

    _member_point_moment_counter = 1

    @classmethod
    def reset_counter(cls) -> None:
        cls._member_point_moment_counter = 1

    def __init__(
        self,
        member: Member,
        load_case: LoadCase,
        magnitude: float = 0.0,
        direction: Tuple[float, float, float] = (0, 0, 1),
        position: float = 0.5,
        axes: str = "global",
        id: Optional[int] = None,
    ) -> None:
        if not (0.0 <= position <= 1.0):
            raise ValueError(f"position must be between 0 and 1: got {position}")

        self.id = id or MemberPointMoment._member_point_moment_counter
        if id is None:
            MemberPointMoment._member_point_moment_counter += 1

        self.member = member
        self.load_case = load_case
        self.magnitude = magnitude
        self.direction = direction
        self.position = position
        self.axes = axes

        self.load_case.add_member_point_moment(self)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "member": self.member.id,
            "load_case": self.load_case.id,
            "magnitude": self.magnitude,
            "direction": self.direction,
            "position": self.position,
            "axes": self.axes,
        }

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        *,
        members: Dict[int, "Member"],
        load_case: "LoadCase",
    ) -> "MemberPointMoment":
        member_id = data.get("member") or data.get("member_id")
        if member_id is None:
            raise ValueError("MemberPointMoment.from_dict: 'member' (id) is required.")
        member = members.get(member_id)
        if member is None:
            raise KeyError(f"MemberPointMoment.from_dict: Member with id={member_id} not found.")

        magnitude = data.get("magnitude", 0.0)
        direction = tuple(data.get("direction", (0.0, 0.0, 1.0)))
        position = data.get("position", 0.5)
        axes = data.get("axes", "global")
        moment_id = data.get("id")

        obj = cls(
            member=member,
            load_case=load_case,
            magnitude=magnitude,
            direction=direction,
            position=position,
            axes=axes,
            id=moment_id,
        )

        if moment_id is not None and moment_id >= cls._member_point_moment_counter:
            cls._member_point_moment_counter = moment_id + 1

        return obj
