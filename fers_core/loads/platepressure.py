from typing import Dict, Any, Optional, Tuple

from fers_core.loads.loadcase import LoadCase


class PlatePressure:
    """
    A pressure load applied to a plate surface or a single generated plate element.

    Attributes:
        id (int): Unique identifier.
        load_case (LoadCase): The load case this pressure belongs to.
        magnitude (float): Pressure magnitude (force/area).
        direction (tuple): Pressure direction unit vector.
        surface_id (int | None): Target a whole surface (all its generated elements).
        plate_element_id (int | None): Target a single generated plate element.
        projected (bool | None): When true the pressure acts on the area projected
            onto ``direction`` (e.g. snow), otherwise on the true element area.
    """

    _plate_pressure_counter = 1

    @classmethod
    def reset_counter(cls) -> None:
        cls._plate_pressure_counter = 1

    def __init__(
        self,
        load_case: LoadCase,
        magnitude: float = 0.0,
        direction: Tuple[float, float, float] = (0, 0, -1),
        surface_id: Optional[int] = None,
        plate_element_id: Optional[int] = None,
        projected: Optional[bool] = None,
        id: Optional[int] = None,
    ) -> None:
        self.id = id or PlatePressure._plate_pressure_counter
        if id is None:
            PlatePressure._plate_pressure_counter += 1

        self.load_case = load_case
        self.magnitude = magnitude
        self.direction = direction
        self.surface_id = surface_id
        self.plate_element_id = plate_element_id
        self.projected = projected

        self.load_case.add_plate_pressure(self)

    def to_dict(self) -> Dict[str, Any]:
        # Exactly one target — serialized as a tagged `target` object.
        if self.surface_id is not None:
            target = {"kind": "Surface", "surface_id": self.surface_id}
        elif self.plate_element_id is not None:
            target = {"kind": "Element", "plate_element_id": self.plate_element_id}
        else:
            raise ValueError(
                "PlatePressure requires exactly one of surface_id or plate_element_id."
            )
        data: Dict[str, Any] = {
            "id": self.id,
            "target": target,
            "magnitude": self.magnitude,
            "direction": self.direction,
        }
        if self.projected is not None:
            data["projected"] = self.projected
        return data

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        *,
        load_case: "LoadCase",
    ) -> "PlatePressure":
        pressure_id = data.get("id")
        target = data.get("target", {}) or {}
        obj = cls(
            load_case=load_case,
            magnitude=data.get("magnitude", 0.0),
            direction=tuple(data.get("direction", (0.0, 0.0, -1.0))),
            surface_id=target.get("surface_id"),
            plate_element_id=target.get("plate_element_id"),
            projected=data.get("projected"),
            id=pressure_id,
        )
        if pressure_id is not None and pressure_id >= cls._plate_pressure_counter:
            cls._plate_pressure_counter = pressure_id + 1
        return obj
