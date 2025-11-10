from typing import Dict, Any, Tuple

from fers_core.loads.loadcase import LoadCase
from ..nodes.node import Node


class NodalMoment:
    _nodal_moment_counter = 1

    def __init__(self, node: Node, load_case, magnitude: float, direction: Tuple[float, float, float]):
        """
        Initialize a nodal moment load.

        Args:
            node (Node): The node where the moment is applied.
            load_case: The load case that this moment belongs to.
            magnitude (float): The magnitude of the moment (in Nm).
            direction (tuple): The moment direction in the global reference frame
                               (e.g., (Mx, My, Mz) for moment components about X, Y, Z axes).
        """
        self.id = NodalMoment._nodal_moment_counter
        NodalMoment._nodal_moment_counter += 1
        self.node = node
        self.load_case = load_case
        self.magnitude = magnitude
        self.direction = direction
        self.load_type = "moment"

        # Automatically add this nodal moment to the load case upon creation
        self.load_case.add_nodal_moment(self)

    @classmethod
    def reset_counter(cls):
        cls._nodal_moment_counter = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "node": self.node.id,
            "load_case": self.load_case.id,
            "magnitude": self.magnitude,
            "direction": self.direction,
            "load_type": self.load_type,
        }

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        *,
        nodes: Dict[int, "Node"],
        load_case: "LoadCase",
    ) -> "NodalMoment":
        node_id = data.get("node") or data.get("node_id")
        if node_id is None:
            raise ValueError("NodalMoment.from_dict: 'node' (id) is required.")
        node = nodes.get(node_id)
        if node is None:
            raise KeyError(f"NodalMoment.from_dict: Node with id={node_id} not found.")

        magnitude = data.get("magnitude", 0.0)
        direction = tuple(data.get("direction", (0.0, 0.0, 0.0)))  # (Mx,My,Mz)

        obj = cls(node=node, load_case=load_case, magnitude=magnitude, direction=direction)

        moment_id = data.get("id")
        if moment_id is not None:
            obj.id = moment_id
            if moment_id >= cls._nodal_moment_counter:
                cls._nodal_moment_counter = moment_id + 1

        return obj

    def __repr__(self) -> str:
        return (
            f"NodalMoment(id={self.id}, node={self.node.id}, "
            f"load_case={self.load_case.id}, magnitude={self.magnitude}, "
            f"direction={self.direction}, load_type={self.load_type})"
        )
