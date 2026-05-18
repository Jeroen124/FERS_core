from __future__ import annotations

from dataclasses import field
from typing import Any, Dict

from fers_core.results.nodes import NodeDisplacement, NodeForces, NodeLocation


class PlateResultants:
    nx: float = 0.0
    ny: float = 0.0
    nxy: float = 0.0
    mx: float = 0.0
    my: float = 0.0
    mxy: float = 0.0
    qx: float = 0.0
    qy: float = 0.0

    @classmethod
    def from_pydantic(cls, pyd_object: Any) -> "PlateResultants":
        instance = cls()
        instance.nx = float(getattr(pyd_object, "nx", 0.0))
        instance.ny = float(getattr(pyd_object, "ny", 0.0))
        instance.nxy = float(getattr(pyd_object, "nxy", 0.0))
        instance.mx = float(getattr(pyd_object, "mx", 0.0))
        instance.my = float(getattr(pyd_object, "my", 0.0))
        instance.mxy = float(getattr(pyd_object, "mxy", 0.0))
        instance.qx = float(getattr(pyd_object, "qx", 0.0))
        instance.qy = float(getattr(pyd_object, "qy", 0.0))
        return instance

    def to_dict(self) -> Dict[str, float]:
        return {
            "nx": self.nx,
            "ny": self.ny,
            "nxy": self.nxy,
            "mx": self.mx,
            "my": self.my,
            "mxy": self.mxy,
            "qx": self.qx,
            "qy": self.qy,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlateResultants":
        instance = cls()
        instance.nx = float(data.get("nx", 0.0))
        instance.ny = float(data.get("ny", 0.0))
        instance.nxy = float(data.get("nxy", 0.0))
        instance.mx = float(data.get("mx", 0.0))
        instance.my = float(data.get("my", 0.0))
        instance.mxy = float(data.get("mxy", 0.0))
        instance.qx = float(data.get("qx", 0.0))
        instance.qy = float(data.get("qy", 0.0))
        return instance


class PlateResult:
    plate_id: int = 0
    centroid: NodeLocation = field(default_factory=NodeLocation)
    centroid_displacement_global: NodeDisplacement = field(default_factory=NodeDisplacement)
    centroid_displacement_local: NodeDisplacement = field(default_factory=NodeDisplacement)
    resultants: PlateResultants = field(default_factory=PlateResultants)
    nodal_forces_global: Dict[str, NodeForces] = field(default_factory=dict)

    @classmethod
    def from_pydantic(cls, pyd_object: Any) -> "PlateResult":
        instance = cls()
        instance.plate_id = int(getattr(pyd_object, "plate_id", 0) or 0)
        instance.centroid = NodeLocation.from_pydantic(getattr(pyd_object, "centroid", None))
        instance.centroid_displacement_global = NodeDisplacement.from_pydantic(
            getattr(pyd_object, "centroid_displacement_global", None)
        )
        instance.centroid_displacement_local = NodeDisplacement.from_pydantic(
            getattr(pyd_object, "centroid_displacement_local", None)
        )
        instance.resultants = PlateResultants.from_pydantic(getattr(pyd_object, "resultants", None))
        instance.nodal_forces_global = {
            str(key): NodeForces.from_pydantic(value)
            for key, value in (getattr(pyd_object, "nodal_forces_global", {}) or {}).items()
        }
        return instance

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plate_id": self.plate_id,
            "centroid": self.centroid.to_dict(),
            "centroid_displacement_global": self.centroid_displacement_global.to_dict(),
            "centroid_displacement_local": self.centroid_displacement_local.to_dict(),
            "resultants": self.resultants.to_dict(),
            "nodal_forces_global": {key: value.to_dict() for key, value in self.nodal_forces_global.items()},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlateResult":
        instance = cls()
        instance.plate_id = int(data.get("plate_id", 0) or 0)
        instance.centroid = NodeLocation.from_pydantic(
            type("NodeLocationProxy", (), data.get("centroid", {}))()
        )
        instance.centroid_displacement_global = NodeDisplacement.from_pydantic(
            type("NodeDispProxy", (), data.get("centroid_displacement_global", {}))()
        )
        instance.centroid_displacement_local = NodeDisplacement.from_pydantic(
            type("NodeDispProxy", (), data.get("centroid_displacement_local", {}))()
        )
        instance.resultants = PlateResultants.from_dict(data.get("resultants", {}))
        instance.nodal_forces_global = {
            str(key): NodeForces.from_pydantic(type("NodeForcesProxy", (), value)())
            for key, value in (data.get("nodal_forces_global") or {}).items()
        }
        return instance
