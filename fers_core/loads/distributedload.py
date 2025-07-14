# distributed_load.py
from typing import Optional, Dict, Any, Tuple
from ..members.member import Member
from ..loads.loadcase import LoadCase
from ..loads.distributionshape import DistributionShape


class DistributedLoad:
    """
    Represents a line load applied along a member, which can be uniform, triangular, or inverse triangular.

    Attributes:
        id (int): Unique identifier for the load.
        member (Member): The member on which the load is applied.
        load_case (LoadCombination): The load case to which this load belongs.
        distribution_shape (DistributionShape): The shape of the load distribution (uniform, triangular,
            or inverse_triangular.).
        magnitude (float): The load magnitude at end_pos (N/m).
        direction (Tuple[float, float, float]): The load direction as a 3-tuple in the
            global coordinate system.
        start_pos (float): The start position along the member's length (in meters).
        end_pos (float): The end position along the member's length (in meters).
    """

    _distributed_load_counter = 1

    def __init__(
        self,
        member: Member,
        load_case: LoadCase,
        distribution_shape: DistributionShape = DistributionShape.UNIFORM,
        magnitude: float = 0.0,
        direction: Tuple[float, float, float] = (0, -1, 0),
        start_pos: float = 0,
        end_pos: Optional[float] = 1,
        id: Optional[int] = None,
    ) -> None:
        """
        Initialize a distributed load along a member.

        Args:
            member: The member to which the load is applied.
            load_case: The load case this load belongs to.
            distribution_shape: The shape of the distribution (uniform, triangular, inverse_triangular).
            magnitude: Load magnitude (N/m) at the end_pos of the member segment.
            direction: The direction of the load in global coordinates (default: (0, -1, 0) = downward).
            start_pos: The start position along the member length in meters (default 0.0).
            end_pos: The end position along the member length in meters (default 1.0).
            load_type: A descriptor for the load type (default: "distributed").
            id: Optional unique identifier. If None, auto-increment.
        """
        self.id = id or DistributedLoad._distributed_load_counter
        if id is None:
            DistributedLoad._distributed_load_counter += 1

        self.member = member
        self.load_case = load_case
        self.distribution_shape = distribution_shape
        self.magnitude = magnitude
        self.direction = direction
        self.start_pos = start_pos
        self.end_pos = end_pos

        self.load_case.add_distributed_load(self)

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize the distributed load into a dictionary for JSON output.
        """
        return {
            "id": self.id,
            "member": self.member.id,
            "load_case": self.load_case.id,
            "distribution_shape": self.distribution_shape.value,
            "magnitude": self.magnitude,
            "direction": self.direction,
            "start_pos": self.start_pos,
            "end_pos": self.end_pos,
        }
