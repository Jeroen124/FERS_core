from typing import List, Optional
from FERS_core.supports.nodalsupport import NodalSupport


class Node:
    _node_counter = 1

    def __init__(
        self,
        X: float = 0.0,
        Y: float = 0.0,
        Z: float = 0.0,
        id: Optional[int] = None,
        classification: str = "",
        nodal_support: Optional[NodalSupport] = None,
    ):
        self.X = X
        self.Y = Y
        self.Z = Z
        self.id = id or Node._node_counter
        if id is None:
            Node._node_counter += 1
        self.classification = classification
        self.nodal_support = nodal_support

    def to_dict(self):
        return {
            "id": self.id,
            "classification": self.classification,
            "X": self.X,
            "Y": self.Y,
            "Z": self.Z,
            "nodal_support": self.nodal_support.id if self.nodal_support else None,
        }

    @classmethod
    def reset_counter(cls) -> None:
        cls._node_counter = 1

    @staticmethod
    def find_at_location(
        nodes: List["Node"], X: float, Y: float, Z: float, tolerance: float = 1e-3
    ) -> List["Node"]:
        """
        Find all nodes at a specific location within a given tolerance.

        :param nodes: A list of Node instances to search through.
        :param x: The X coordinate of the location.
        :param y: The Y coordinate of the location.
        :param z: The Z coordinate of the location.
        :param tolerance: The tolerance within which coordinates are considered equal.
        :return: A list of Node instances at the given location.
        """
        if not all(isinstance(node) for node in nodes):
            raise TypeError("All elements in 'nodes' must be instances of Node.")

        return [
            node
            for node in nodes
            if abs(node.X - X) <= tolerance and abs(node.Y - Y) <= tolerance and abs(node.Z - Z) <= tolerance
        ]

    @staticmethod
    def distance(node1: "Node", node2: "Node") -> float:
        return ((node1.X - node2.X) ** 2 + (node1.Y - node2.Y) ** 2 + (node1.Z - node2.Z) ** 2) ** 0.5

    @staticmethod
    def find_closest(nodes: List["Node"], X: float, Y: float, Z: float) -> "Node":
        if not all(isinstance(node, Node) for node in nodes):
            raise TypeError("All elements in 'nodes' must be instances of Node.")
        return min(
            nodes,
            key=lambda node: ((node.X - X) ** 2 + (node.Y - Y) ** 2 + (node.Z - Z) ** 2) ** 0.5,
        )
