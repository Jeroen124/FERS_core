from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from .loadcase import LoadCase


@dataclass
class SurfaceLoadVertex:
    x: float
    y: float
    z: float

    def to_dict(self) -> Dict[str, float]:
        return {"x": self.x, "y": self.y, "z": self.z}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SurfaceLoadVertex":
        return cls(x=float(data["x"]), y=float(data["y"]), z=float(data["z"]))


class SurfaceLoad:
    _surface_load_counter = 1

    def __init__(
        self,
        load_case: "LoadCase",
        polygon: Iterable[SurfaceLoadVertex | Dict[str, Any] | Tuple[float, float, float]],
        magnitude: float,
        direction: Tuple[float, float, float] = (0.0, -1.0, 0.0),
        distribution_direction: Optional[Tuple[float, float, float]] = None,
        id: Optional[int] = None,
    ) -> None:
        self.id = id or SurfaceLoad._surface_load_counter
        if id is None:
            SurfaceLoad._surface_load_counter += 1

        self.load_case = load_case
        self.polygon = [self._coerce_vertex(vertex) for vertex in polygon]
        self.magnitude = magnitude
        self.direction = direction
        self.distribution_direction = distribution_direction

        self.load_case.add_surface_load(self)

    @staticmethod
    def _coerce_vertex(
        vertex: SurfaceLoadVertex | Dict[str, Any] | Tuple[float, float, float],
    ) -> SurfaceLoadVertex:
        if isinstance(vertex, SurfaceLoadVertex):
            return vertex
        if isinstance(vertex, dict):
            return SurfaceLoadVertex.from_dict(vertex)
        if isinstance(vertex, (tuple, list)) and len(vertex) == 3:
            x, y, z = vertex
            return SurfaceLoadVertex(float(x), float(y), float(z))
        raise TypeError(
            "SurfaceLoad polygon vertices must be SurfaceLoadVertex, dict, or 3-item tuple/list."
        )

    @classmethod
    def reset_counter(cls) -> None:
        cls._surface_load_counter = 1

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "id": self.id,
            "load_case": self.load_case.id,
            "polygon": [vertex.to_dict() for vertex in self.polygon],
            "magnitude": self.magnitude,
            "direction": self.direction,
        }
        if self.distribution_direction is not None:
            data["distribution_direction"] = self.distribution_direction
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any], *, load_case: "LoadCase") -> "SurfaceLoad":
        polygon = [SurfaceLoadVertex.from_dict(vertex) for vertex in data.get("polygon", [])]
        direction = tuple(data.get("direction", (0.0, -1.0, 0.0)))
        distribution_direction_raw = data.get("distribution_direction")
        distribution_direction = (
            tuple(distribution_direction_raw) if distribution_direction_raw is not None else None
        )
        load_id = data.get("id")

        obj = cls(
            load_case=load_case,
            polygon=polygon,
            magnitude=data.get("magnitude", 0.0),
            direction=direction,
            distribution_direction=distribution_direction,
            id=load_id,
        )

        if load_id is not None and load_id >= cls._surface_load_counter:
            cls._surface_load_counter = load_id + 1

        return obj
