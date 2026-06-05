from __future__ import annotations

from typing import Dict, Optional, TYPE_CHECKING, Union

from ..members.material import Material
from ..nodes.node import Node
from .components import (
    PlaneState,
    PlateBehavior,
    PlateStiffnessModifiers,
    PlateTheory,
    _normalize_enum,
    normalize_plate_behavior,
)

if TYPE_CHECKING:
    from .platesurface import PlateSurface


class PlateElement:
    """
    A single FEM plate element (TRI3 or QUAD4) referencing model nodes by id.

    Mirrors the solver's ``PlateElement`` schema.  Historically this class was
    named ``Plate``; that name is kept as an alias for backwards compatibility.
    """

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
        behavior: Union[PlateBehavior, str, None] = None,
        theory: Union[PlateTheory, str, None] = None,
        plane_state: Union[PlaneState, str, None] = None,
        offset: Optional[float] = None,
        stiffness_modifiers: Optional[PlateStiffnessModifiers] = None,
    ) -> None:
        if len(nodes) not in {3, 4}:
            raise ValueError("PlateElement currently supports TRI3 or QUAD4 topology.")
        if thickness <= 0.0:
            raise ValueError("PlateElement thickness must be positive.")

        self.id = id or PlateElement._plate_counter
        if id is None:
            PlateElement._plate_counter += 1

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
        self.behavior = normalize_plate_behavior(behavior)
        self.theory = _normalize_enum(PlateTheory, theory)
        self.plane_state = _normalize_enum(PlaneState, plane_state)
        self.offset = float(offset) if offset is not None else None
        self.stiffness_modifiers = stiffness_modifiers

    @classmethod
    def reset_counter(cls) -> None:
        cls._plate_counter = 1

    def to_dict(self) -> Dict:
        # Optional fields are omitted when unset: the solver's PlateElement uses
        # plain (non-nullable) defaults for `behavior`/`offset` and rejects null.
        data = {
            "id": self.id,
            "node_ids": [node.id for node in self.nodes],
            "material": self.material.id,
            "thickness": self.thickness,
        }
        if self.behavior is not None:
            data["behavior"] = self.behavior.value
        if self.theory is not None:
            data["theory"] = self.theory.value
        if self.plane_state is not None:
            data["plane_state"] = self.plane_state.value
        if self.offset is not None:
            data["offset"] = self.offset
        if self.source_surface_id is not None:
            data["source_surface_id"] = self.source_surface_id
        if self.stiffness_modifiers is not None:
            data["stiffness_modifiers"] = self.stiffness_modifiers.to_dict()
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
    ) -> "PlateElement":
        plate_nodes = [nodes_by_id[node_id] for node_id in data["node_ids"]]

        material_id = data.get("material")
        if material_id is None:
            raise ValueError("PlateElement material is required.")
        material = materials_by_id[material_id]

        source_surface_id = data.get("source_surface_id")
        source_surface = (
            source_surfaces_by_id.get(source_surface_id)
            if source_surface_id is not None and source_surfaces_by_id is not None
            else None
        )

        return cls(
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
            behavior=data.get("behavior"),
            theory=data.get("theory"),
            plane_state=data.get("plane_state"),
            offset=data.get("offset"),
            stiffness_modifiers=PlateStiffnessModifiers.from_dict(data.get("stiffness_modifiers")),
        )


# Backwards-compatible alias: the FEM plate element used to be called ``Plate``.
Plate = PlateElement
