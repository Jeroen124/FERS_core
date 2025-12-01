# distributed_load.py
from typing import Optional, Dict, Any, Tuple
from ..members.member import Member
from ..loads.loadcase import LoadCase


class DistributedLoad:
    """
    Represents a line load applied along a member with linear variation.

    The load varies linearly from 'magnitude' at start_frac to 'end_magnitude' at end_frac.
    - Uniform load: magnitude == end_magnitude
    - Triangular load: one of them is 0
    - General linear variation: any two different values

    Attributes:
        id (int): Unique identifier for the load.
        member (Member): The member on which the load is applied.
        load_case (LoadCombination): The load case to which this load belongs.
        magnitude (float): The load intensity (N/m) at start_frac.
        end_magnitude (float): The load intensity (N/m) at end_frac.
        direction (Tuple[float, float, float]): The load direction as a 3-tuple in the
            global coordinate system.
        start_frac (float): The start position along the member's length as a fraction (default 0.0).
        end_frac (float): The end position along the member's length as a fraction (default 1.0).
    """

    _distributed_load_counter = 1

    def __init__(
        self,
        member: Member,
        load_case: LoadCase,
        magnitude: float = 0.0,
        end_magnitude: Optional[float] = None,
        direction: Tuple[float, float, float] = (0, -1, 0),
        start_frac: float = 0.0,
        end_frac: float = 1.0,
        id: Optional[int] = None,
    ) -> None:
        """
        Initialize a distributed load along a member.

        Args:
            member: The member to which the load is applied.
            load_case: The load case this load belongs to.
            magnitude: Load intensity (N/m) at start_frac.
            end_magnitude: Load intensity (N/m) at end_frac. If None, defaults to magnitude (uniform load).
            direction: The direction of the load in global coordinates (default: (0, -1, 0) = downward).
            start_frac: The start position along the member as a fraction of the length (default 0.0).
            end_frac: The end position along the member as a fraction of the length (default 1.0).
            id: Optional unique identifier. If None, auto-increment.
        """

        if not (0.0 <= start_frac <= 1.0) or not (0.0 <= end_frac <= 1.0):
            raise ValueError(
                f"start_frac and end_frac must both be between 0 and 1: "
                f"got start_frac={start_frac}, end_frac={end_frac}"
            )

        self.id = id or DistributedLoad._distributed_load_counter
        if id is None:
            DistributedLoad._distributed_load_counter += 1

        if end_magnitude is None:
            end_magnitude = magnitude

        self.member = member
        self.load_case = load_case
        self.magnitude = magnitude
        self.end_magnitude = end_magnitude
        self.direction = direction
        self.start_frac = start_frac
        self.end_frac = end_frac

        self.load_case.add_distributed_load(self)

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize the distributed load into a dictionary for JSON output.
        """
        return {
            "member": self.member.id,
            "load_case": self.load_case.id,
            "magnitude": self.magnitude,
            "end_magnitude": self.end_magnitude,
            "direction": self.direction,
            "start_frac": self.start_frac,
            "end_frac": self.end_frac,
        }

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        *,
        members: Dict[int, "Member"],
        load_case: "LoadCase",
    ) -> "DistributedLoad":
        member_id = data.get("member") or data.get("member_id")
        if member_id is None:
            raise ValueError("DistributedLoad.from_dict: 'member' (id) is required.")
        member = members.get(member_id)
        if member is None:
            raise KeyError(f"DistributedLoad.from_dict: Member with id={member_id} not found.")

        magnitude = data.get("magnitude", 0.0)
        end_magnitude = data.get("end_magnitude")
        direction = tuple(data.get("direction", (0.0, -1.0, 0.0)))
        start_frac = data.get("start_frac", 0.0)
        end_frac = data.get("end_frac", 1.0)
        load_id = data.get("id")

        obj = cls(
            member=member,
            load_case=load_case,
            magnitude=magnitude,
            end_magnitude=end_magnitude,
            direction=direction,
            start_frac=start_frac,
            end_frac=end_frac,
            id=load_id,
        )

        if load_id is not None and load_id >= cls._distributed_load_counter:
            cls._distributed_load_counter = load_id + 1

        return obj
