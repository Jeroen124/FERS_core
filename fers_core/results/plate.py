from __future__ import annotations

from typing import Any, Dict, Optional

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
    centroid: NodeLocation
    centroid_displacement_global: NodeDisplacement
    centroid_displacement_local: NodeDisplacement
    resultants: PlateResultants
    nodal_forces_global: Dict[str, NodeForces]

    # Real defaults: as ReactionNodeResult, these were `field(default_factory=...)`
    # on a class that is not a dataclass, so they read back `dataclasses.Field`.
    def __init__(
        self,
        plate_id: int = 0,
        centroid: Optional[NodeLocation] = None,
        centroid_displacement_global: Optional[NodeDisplacement] = None,
        centroid_displacement_local: Optional[NodeDisplacement] = None,
        resultants: Optional[PlateResultants] = None,
        nodal_forces_global: Optional[Dict[str, NodeForces]] = None,
    ) -> None:
        self.plate_id = plate_id
        self.centroid = centroid if centroid is not None else NodeLocation()
        self.centroid_displacement_global = (
            centroid_displacement_global if centroid_displacement_global is not None else NodeDisplacement()
        )
        self.centroid_displacement_local = (
            centroid_displacement_local if centroid_displacement_local is not None else NodeDisplacement()
        )
        self.resultants = resultants if resultants is not None else PlateResultants()
        self.nodal_forces_global = nodal_forces_global if nodal_forces_global is not None else {}

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
