from __future__ import annotations

from typing import Dict, Optional, TYPE_CHECKING

from ..members.material import Material
from ..nodes.node import Node

if TYPE_CHECKING:
    from .platesurface import PlateSurface


class Plate:
    _plate_counter = 1

    def __init__(
        self,
        nodes: list[Node],
        material: Material,
        thickness: float,
        id: Optional[int] = None,
        classification: str = "",
        source_surface: Optional["PlateSurface"] = None,
        source_surface_id: Optional[int] = None,
        local_x_direction: Optional[tuple[float, float, float]] = None,
    ) -> None:
        if len(nodes) not in {3, 4}:
            raise ValueError("Plate currently supports TRI3 or QUAD4 topology.")
        if thickness <= 0.0:
            raise ValueError("Plate thickness must be positive.")

        self.id = id or Plate._plate_counter
        if id is None:
            Plate._plate_counter += 1

        self.nodes = nodes
        self.material = material
        self.thickness = float(thickness)
        self.classification = classification
        self.source_surface = source_surface
        self.source_surface_id = (
            source_surface_id
            if source_surface_id is not None
            else (source_surface.id if source_surface is not None else None)
        )
        self.local_x_direction = local_x_direction

    @classmethod
    def reset_counter(cls) -> None:
        cls._plate_counter = 1

    def to_dict(self) -> Dict:
        data = {
            "id": self.id,
            "node_ids": [node.id for node in self.nodes],
            "material": self.material.id,
            "thickness": self.thickness,
            "classification": self.classification,
        }
        if self.source_surface_id is not None:
            data["source_surface"] = self.source_surface_id
        if self.local_x_direction is not None:
            data["local_x_direction"] = self.local_x_direction
        return data

    @classmethod
    def from_dict(
        cls,
        data: Dict,
        *,
        nodes_by_id: dict[int, Node],
        materials_by_id: dict[int, Material],
        nodal_supports_by_id: dict[int, object] | None = None,
        source_surfaces_by_id: dict[int, "PlateSurface"] | None = None,
    ) -> "Plate":
        if data.get("node_ids") is not None:
            plate_nodes = [nodes_by_id[node_id] for node_id in data["node_ids"]]
        else:
            # Legacy format: nodes embedded as full dicts.
            plate_nodes = [
                Node.get_or_create_from_dict(
                    node_data,
                    nodes_by_id=nodes_by_id,
                    nodal_supports_by_id=nodal_supports_by_id,
                )
                for node_data in data.get("nodes", [])
            ]

        material_id = data.get("material")
        if material_id is None:
            raise ValueError("Plate material is required.")
        material = materials_by_id[material_id]

        source_surface_id = data.get("source_surface")
        source_surface = (
            source_surfaces_by_id.get(source_surface_id)
            if source_surface_id is not None and source_surfaces_by_id is not None
            else None
        )

        plate = cls(
            id=data.get("id"),
            nodes=plate_nodes,
            material=material,
            thickness=float(data["thickness"]),
            classification=data.get("classification", ""),
            source_surface=source_surface,
            source_surface_id=source_surface_id,
            local_x_direction=tuple(data["local_x_direction"])
            if data.get("local_x_direction") is not None
            else None,
        )
        return plate
