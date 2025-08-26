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
        start_frac (float): The start position along the member's length as a fraction (default 0.0).
        end_frac (float): The end position along the member's length as a fraction (default 1.0).
    """

    _distributed_load_counter = 1

    def __init__(
        self,
        member: Member,
        load_case: LoadCase,
        distribution_shape: DistributionShape = DistributionShape.UNIFORM,
        magnitude: float = 0.0,
        direction: Tuple[float, float, float] = (0, -1, 0),
        start_frac: float = 0.0,
        end_frac: float = 1.0,
        end_magnitude: Optional[float] = None,
        id: Optional[int] = None,
    ) -> None:
        """
        Initialize a distributed load along a member.

        Args:
            member: The member to which the load is applied.
            load_case: The load case this load belongs to.
            distribution_shape: The shape of the distribution (uniform, triangular, inverse_triangular).
            magnitude: Load magnitude (N/m) at the end_frac of the member segment.
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
        if start_frac >= end_frac:
            raise ValueError(
                f"start_frac ({start_frac}) cannot be greater or equal than end_frac ({end_frac})"
            )

        self.id = id or DistributedLoad._distributed_load_counter
        if id is None:
            DistributedLoad._distributed_load_counter += 1

        if end_magnitude is None:
            end_magnitude = magnitude

        self.member = member
        self.load_case = load_case

        if isinstance(distribution_shape, str):
            try:
                distribution_shape = DistributionShape[distribution_shape]
            except KeyError:
                raise ValueError(
                    f"Invalid distribution_shape '{distribution_shape}'. "
                    f"Must be one of {[s.name for s in DistributionShape]}"
                )

        self.distribution_shape = distribution_shape
        self.magnitude = magnitude
        self.direction = direction
        self.start_frac = start_frac
        self.end_frac = end_frac

        self.load_case.add_distributed_load(self)
        self.end_magnitude = end_magnitude

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
            "start_frac": self.start_frac,
            "end_frac": self.end_frac,
            "end_magnitude": self.end_magnitude,
        }
