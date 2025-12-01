from typing import Dict, Any

from fers_core.loads.loadcase import LoadCase
from fers_core.nodes.node import Node


class NodalLoad:
    _nodal_load_counter = 1

    def __init__(self, node, load_case, magnitude: float, direction: tuple, load_type: str = "force"):
        """
        Initialize a nodal load.

        Args:
            node (Node): The node the load is applied to.
            load_case (LoadCase): The load case this load belongs to.
            magnitude (float): The magnitude of the load.
            direction (tuple): The direction of the load in global reference frame as a tuple (X, Y, Z).
            load_type (str, optional): The type of the load ('force' or 'moment'). Defaults to 'force'.
        """
        self.id = NodalLoad._nodal_load_counter
        NodalLoad._nodal_load_counter += 1
        self.node = node
        self.load_case = load_case
        self.magnitude = magnitude
        self.direction = direction
        self.load_type = load_type

        # Automatically add this nodal load to the load case upon creation
        self.load_case.add_nodal_load(self)

    @classmethod
    def reset_counter(cls):
        cls._nodal_load_counter = 1

    def to_dict(self):
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
    ) -> "NodalLoad":
        node_id = data.get("node") or data.get("node_id")
        if node_id is None:
            raise ValueError("NodalLoad.from_dict: 'node' (id) is required.")
        node = nodes.get(node_id)
        if node is None:
            raise KeyError(f"NodalLoad.from_dict: Node with id={node_id} not found.")

        magnitude = data.get("magnitude", 0.0)
        direction = tuple(data.get("direction", (0.0, 0.0, 0.0)))
        load_type = data.get("load_type", "force")

        obj = cls(
            node=node, load_case=load_case, magnitude=magnitude, direction=direction, load_type=load_type
        )

        load_id = data.get("id")
        if load_id is not None:
            obj.id = load_id
            if load_id >= cls._nodal_load_counter:
                cls._nodal_load_counter = load_id + 1

        return obj
