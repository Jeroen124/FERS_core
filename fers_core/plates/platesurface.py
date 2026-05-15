from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional, TYPE_CHECKING

from ..members.material import Material
from ..nodes.node import Node
from .mesh import triangulate_surface_polygon

if TYPE_CHECKING:
    from .plate import Plate


@dataclass
class PlateVertex:
    x: float
    y: float
    z: float

    def to_dict(self) -> Dict[str, float]:
        return {"x": self.x, "y": self.y, "z": self.z}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlateVertex":
        return cls(x=float(data["x"]), y=float(data["y"]), z=float(data["z"]))


class PlateSurface:
    _plate_surface_counter = 1

    def __init__(
        self,
        polygon: Iterable[PlateVertex | Dict[str, Any] | tuple[float, float, float]],
        material: Material,
        thickness: float,
        *,
        mesh_size: Optional[float] = None,
        name: str = "",
        classification: str = "",
        local_x_direction: Optional[tuple[float, float, float]] = None,
        generated_plate_ids: Optional[list[int]] = None,
        id: Optional[int] = None,
    ) -> None:
        if thickness <= 0.0:
            raise ValueError("PlateSurface thickness must be positive.")

        self.id = id or PlateSurface._plate_surface_counter
        if id is None:
            PlateSurface._plate_surface_counter += 1

        self.polygon = [self._coerce_vertex(vertex) for vertex in polygon]
        self.material = material
        self.thickness = float(thickness)
        self.mesh_size = float(mesh_size) if mesh_size is not None else None
        self.name = name
        self.classification = classification
        self.local_x_direction = local_x_direction
        self.generated_plate_ids = generated_plate_ids[:] if generated_plate_ids is not None else []

    @classmethod
    def reset_counter(cls) -> None:
        cls._plate_surface_counter = 1

    @staticmethod
    def _coerce_vertex(
        vertex: PlateVertex | Dict[str, Any] | tuple[float, float, float],
    ) -> PlateVertex:
        if isinstance(vertex, PlateVertex):
            return vertex
        if isinstance(vertex, dict):
            return PlateVertex.from_dict(vertex)
        if isinstance(vertex, (list, tuple)) and len(vertex) == 3:
            return PlateVertex(float(vertex[0]), float(vertex[1]), float(vertex[2]))
        raise TypeError("PlateSurface vertices must be PlateVertex, dict, or 3-item tuple/list.")

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "polygon": [vertex.to_dict() for vertex in self.polygon],
            "material": self.material.id,
            "thickness": self.thickness,
            "classification": self.classification,
            "generated_plate_ids": self.generated_plate_ids,
        }
        if self.mesh_size is not None:
            data["mesh_size"] = self.mesh_size
        if self.local_x_direction is not None:
            data["local_x_direction"] = self.local_x_direction
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any], *, materials_by_id: dict[int, Material]) -> "PlateSurface":
        material_id = data.get("material")
        if material_id is None:
            raise ValueError("PlateSurface material is required.")
        material = materials_by_id[material_id]
        return cls(
            id=data.get("id"),
            name=data.get("name", ""),
            polygon=[PlateVertex.from_dict(vertex) for vertex in data.get("polygon", [])],
            material=material,
            thickness=float(data["thickness"]),
            mesh_size=data.get("mesh_size"),
            classification=data.get("classification", ""),
            local_x_direction=tuple(data["local_x_direction"])
            if data.get("local_x_direction") is not None
            else None,
            generated_plate_ids=[int(value) for value in data.get("generated_plate_ids", [])],
        )

    def generate_plates(
        self,
        *,
        next_plate_id: int = 1,
        next_node_id: int = 1,
    ) -> tuple[list["Plate"], int, int]:
        from .plate import Plate

        triangles = triangulate_surface_polygon(
            [(vertex.x, vertex.y, vertex.z) for vertex in self.polygon],
            mesh_size=self.mesh_size,
        )
        node_cache: dict[tuple[float, float, float], Node] = {}
        plates: list[Plate] = []
        generated_plate_ids: list[int] = []

        for triangle in triangles:
            plate_nodes: list[Node] = []
            for x, y, z in triangle:
                key = (round(x, 12), round(y, 12), round(z, 12))
                node = node_cache.get(key)
                if node is None:
                    node = Node(X=x, Y=y, Z=z, id=next_node_id)
                    node_cache[key] = node
                    next_node_id += 1
                plate_nodes.append(node)

            plate = Plate(
                id=next_plate_id,
                nodes=plate_nodes,
                material=self.material,
                thickness=self.thickness,
                classification=self.classification,
                source_surface=self,
                local_x_direction=self.local_x_direction,
            )
            generated_plate_ids.append(plate.id)
            plates.append(plate)
            next_plate_id += 1

        self.generated_plate_ids = generated_plate_ids
        return plates, next_plate_id, next_node_id
