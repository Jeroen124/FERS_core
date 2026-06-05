from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Union, TYPE_CHECKING

from ..members.material import Material
from ..nodes.node import Node
from .components import (
    PlaneState,
    PlateBehavior,
    PlateMeshSettings,
    PlateOpening,
    PlateStiffnessModifiers,
    PlateTheory,
    _normalize_enum,
    normalize_plate_behavior,
)
from .mesh import triangulate_surface_polygon

if TYPE_CHECKING:
    from .plate import PlateElement


@dataclass
class PlateVertex:
    """Legacy free-standing vertex (kept for backwards compatibility)."""

    x: float
    y: float
    z: float

    def to_dict(self) -> Dict[str, float]:
        return {"x": self.x, "y": self.y, "z": self.z}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlateVertex":
        return cls(x=float(data["x"]), y=float(data["y"]), z=float(data["z"]))


class PlateSurface:
    """
    A meshable plate surface bounded by existing model nodes.

    The outer boundary references model nodes by id (counter-clockwise). The
    solver meshes the surface into ``PlateElement``s; a local mesher
    (:meth:`generate_plate_elements`) is also provided for client-side meshing.
    """

    _plate_surface_counter = 1

    def __init__(
        self,
        boundary_nodes: Iterable[Node],
        material: Material,
        thickness: float,
        *,
        behavior: Union[PlateBehavior, str, None] = None,
        theory: Union[PlateTheory, str, None] = None,
        plane_state: Union[PlaneState, str, None] = None,
        mesh: Optional[PlateMeshSettings] = None,
        openings: Optional[List[PlateOpening]] = None,
        offset: Optional[float] = None,
        stiffness_modifiers: Optional[PlateStiffnessModifiers] = None,
        name: Optional[str] = None,
        classification: Optional[str] = None,
        local_x_direction: Optional[tuple[float, float, float]] = None,
        mesh_group_id: Optional[int] = None,
        generated_plate_element_ids: Optional[list[int]] = None,
        id: Optional[int] = None,
    ) -> None:
        if thickness <= 0.0:
            raise ValueError("PlateSurface thickness must be positive.")

        self.id = id or PlateSurface._plate_surface_counter
        if id is None:
            PlateSurface._plate_surface_counter += 1

        self.boundary_nodes = list(boundary_nodes)
        if len(self.boundary_nodes) < 3:
            raise ValueError("PlateSurface requires at least three boundary nodes.")

        self.material = material
        self.thickness = float(thickness)
        self.behavior = normalize_plate_behavior(behavior)
        self.theory = _normalize_enum(PlateTheory, theory)
        self.plane_state = _normalize_enum(PlaneState, plane_state)
        self.mesh = mesh
        self.openings = list(openings) if openings is not None else None
        self.offset = float(offset) if offset is not None else None
        self.stiffness_modifiers = stiffness_modifiers
        self.name = name
        self.classification = classification
        self.local_x_direction = local_x_direction
        self.mesh_group_id = mesh_group_id
        self.generated_plate_element_ids = (
            generated_plate_element_ids[:] if generated_plate_element_ids is not None else []
        )

    @classmethod
    def reset_counter(cls) -> None:
        cls._plate_surface_counter = 1

    def to_dict(self) -> Dict[str, Any]:
        # Optional fields are omitted when unset (the solver uses non-nullable
        # defaults for some of them, e.g. `behavior`/`offset`).
        data: Dict[str, Any] = {
            "id": self.id,
            "boundary_node_ids": [node.id for node in self.boundary_nodes],
            "material": self.material.id,
            "thickness": self.thickness,
            "generated_plate_element_ids": self.generated_plate_element_ids,
        }
        if self.name is not None:
            data["name"] = self.name
        if self.behavior is not None:
            data["behavior"] = self.behavior.value
        if self.theory is not None:
            data["theory"] = self.theory.value
        if self.plane_state is not None:
            data["plane_state"] = self.plane_state.value
        if self.classification is not None:
            data["classification"] = self.classification
        if self.offset is not None:
            data["offset"] = self.offset
        if self.mesh_group_id is not None:
            data["mesh_group_id"] = self.mesh_group_id
        if self.mesh is not None:
            data["mesh"] = self.mesh.to_dict()
        if self.openings is not None:
            data["openings"] = [opening.to_dict() for opening in self.openings]
        if self.stiffness_modifiers is not None:
            data["stiffness_modifiers"] = self.stiffness_modifiers.to_dict()
        if self.local_x_direction is not None:
            data["local_x_direction"] = self.local_x_direction
        return data

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        *,
        materials_by_id: dict[int, Material],
        nodes_by_id: dict[int, Node],
    ) -> "PlateSurface":
        material_id = data.get("material")
        if material_id is None:
            raise ValueError("PlateSurface material is required.")
        material = materials_by_id[material_id]

        boundary_node_ids = data.get("boundary_node_ids") or []
        boundary_nodes = [nodes_by_id[node_id] for node_id in boundary_node_ids]

        openings_data = data.get("openings")
        openings = (
            [PlateOpening.from_dict(o) for o in openings_data] if openings_data is not None else None
        )

        surface = cls(
            id=data.get("id"),
            name=data.get("name"),
            boundary_nodes=boundary_nodes,
            material=material,
            thickness=float(data["thickness"]),
            behavior=data.get("behavior"),
            theory=data.get("theory"),
            plane_state=data.get("plane_state"),
            mesh=PlateMeshSettings.from_dict(data.get("mesh")),
            openings=openings,
            offset=data.get("offset"),
            stiffness_modifiers=PlateStiffnessModifiers.from_dict(data.get("stiffness_modifiers")),
            classification=data.get("classification"),
            local_x_direction=tuple(data["local_x_direction"])
            if data.get("local_x_direction") is not None
            else None,
            mesh_group_id=data.get("mesh_group_id"),
            generated_plate_element_ids=[int(v) for v in data.get("generated_plate_element_ids", [])],
        )
        return surface

    def generate_plate_elements(
        self,
        *,
        next_element_id: int = 1,
        next_node_id: int = 1,
    ) -> tuple[list["PlateElement"], int, int]:
        """
        Triangulate the surface into ``PlateElement``s (client-side meshing).

        Reuses the existing boundary nodes where a generated vertex coincides
        with one, and creates interior nodes as needed.
        """
        from .plate import PlateElement

        target_size = self.mesh.target_size if self.mesh is not None else None
        triangles = triangulate_surface_polygon(
            [(node.X, node.Y, node.Z) for node in self.boundary_nodes],
            mesh_size=target_size,
        )

        node_cache: dict[tuple[float, float, float], Node] = {}
        for node in self.boundary_nodes:
            node_cache[(round(node.X, 9), round(node.Y, 9), round(node.Z, 9))] = node

        elements: list["PlateElement"] = []
        generated_ids: list[int] = []

        for triangle in triangles:
            plate_nodes: list[Node] = []
            for x, y, z in triangle:
                key = (round(x, 9), round(y, 9), round(z, 9))
                node = node_cache.get(key)
                if node is None:
                    node = Node(X=x, Y=y, Z=z, id=next_node_id)
                    node_cache[key] = node
                    next_node_id += 1
                plate_nodes.append(node)

            element = PlateElement(
                id=next_element_id,
                nodes=plate_nodes,
                material=self.material,
                thickness=self.thickness,
                classification=self.classification or "",
                source_surface=self,
                local_x_direction=self.local_x_direction,
                behavior=self.behavior,
                theory=self.theory,
                plane_state=self.plane_state,
                offset=self.offset,
                stiffness_modifiers=self.stiffness_modifiers,
            )
            generated_ids.append(element.id)
            elements.append(element)
            next_element_id += 1

        self.generated_plate_element_ids = generated_ids
        return elements, next_element_id, next_node_id
