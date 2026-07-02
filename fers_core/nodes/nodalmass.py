from typing import Optional, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from .node import Node


class NodalMass:
    """A concentrated (lumped) mass attached to a node, for modal and seismic
    analysis (equipment, added / non-structural mass, floor mass, …).

    ``mass`` is an isotropic translational mass added to the node's three
    translational DOFs; the optional rotary inertias are added to the three
    rotational DOFs. **Units are SI regardless of the model's unit system —
    ``mass`` in kg, inertias in kg·m²** (the same convention as
    ``gravity_factor``), so a nodal mass reads consistently with the structural
    self-mass (``density·area``).

    Mirrors the solver's ``NodalMass`` (``model.nodal_masses``). Pass either a
    ``Node`` instance or a node id as ``node``.
    """

    def __init__(
        self,
        node: Union["Node", int],
        mass: float,
        inertia_x: Optional[float] = None,
        inertia_y: Optional[float] = None,
        inertia_z: Optional[float] = None,
    ):
        self.node = node
        self.mass = mass
        self.inertia_x = inertia_x
        self.inertia_y = inertia_y
        self.inertia_z = inertia_z

    def _node_id(self) -> int:
        # Accept a Node instance or a bare id.
        return getattr(self.node, "id", self.node)

    def to_dict(self) -> dict:
        data = {"node": self._node_id(), "mass": self.mass}
        # Emit rotary inertias only when set (the solver defaults them to 0/None).
        if self.inertia_x is not None:
            data["inertia_x"] = self.inertia_x
        if self.inertia_y is not None:
            data["inertia_y"] = self.inertia_y
        if self.inertia_z is not None:
            data["inertia_z"] = self.inertia_z
        return data

    @classmethod
    def from_dict(cls, data: dict, nodes_by_id: Optional[dict] = None) -> "NodalMass":
        node = data.get("node")
        if nodes_by_id is not None and node in nodes_by_id:
            node = nodes_by_id[node]
        return cls(
            node=node,
            mass=data.get("mass", 0.0),
            inertia_x=data.get("inertia_x"),
            inertia_y=data.get("inertia_y"),
            inertia_z=data.get("inertia_z"),
        )
