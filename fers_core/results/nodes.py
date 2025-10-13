from __future__ import annotations

from dataclasses import field
from typing import Dict, Any

# -------------------------------
# Leaf data classes
# -------------------------------


class NodeDisplacement:
    dx: float = 0.0
    dy: float = 0.0
    dz: float = 0.0
    rx: float = 0.0
    ry: float = 0.0
    rz: float = 0.0

    @classmethod
    def from_pydantic(cls, pyd_object: Any) -> "NodeDisplacement":
        return cls(
            dx=float(getattr(pyd_object, "dx", 0.0) or 0.0),
            dy=float(getattr(pyd_object, "dy", 0.0) or 0.0),
            dz=float(getattr(pyd_object, "dz", 0.0) or 0.0),
            rx=float(getattr(pyd_object, "rx", 0.0) or 0.0),
            ry=float(getattr(pyd_object, "ry", 0.0) or 0.0),
            rz=float(getattr(pyd_object, "rz", 0.0) or 0.0),
        )

    def to_dict(self) -> Dict[str, float]:
        return {
            "dx": self.dx,
            "dy": self.dy,
            "dz": self.dz,
            "rx": self.rx,
            "ry": self.ry,
            "rz": self.rz,
        }


class NodeForces:
    fx: float = 0.0
    fy: float = 0.0
    fz: float = 0.0
    mx: float = 0.0
    my: float = 0.0
    mz: float = 0.0

    def from_pydantic(pyd_object: Any) -> "NodeForces":
        return NodeForces(
            fx=float(getattr(pyd_object, "fx", 0.0) or 0.0),
            fy=float(getattr(pyd_object, "fy", 0.0) or 0.0),
            fz=float(getattr(pyd_object, "fz", 0.0) or 0.0),
            mx=float(getattr(pyd_object, "mx", 0.0) or 0.0),
            my=float(getattr(pyd_object, "my", 0.0) or 0.0),
            mz=float(getattr(pyd_object, "mz", 0.0) or 0.0),
        )

    def to_dict(self) -> Dict[str, float]:
        return {
            "fx": self.fx,
            "fy": self.fy,
            "fz": self.fz,
            "mx": self.mx,
            "my": self.my,
            "mz": self.mz,
        }


class NodeLocation:
    X: float = 0.0
    Y: float = 0.0
    Z: float = 0.0

    @classmethod
    def from_pydantic(cls, pyd_object: Any) -> "NodeLocation":
        return cls(
            X=float(getattr(pyd_object, "X", 0.0) or 0.0),
            Y=float(getattr(pyd_object, "Y", 0.0) or 0.0),
            Z=float(getattr(pyd_object, "Z", 0.0) or 0.0),
        )

    def to_dict(self) -> Dict[str, float]:
        return {"X": self.X, "Y": self.Y, "Z": self.Z}


class ReactionNodeResult:
    location: NodeLocation = field(default_factory=NodeLocation)
    nodal_forces: NodeForces = field(default_factory=NodeForces)
    support_id: int = 0

    @classmethod
    def from_pydantic(cls, pyd_object: Any) -> "ReactionNodeResult":
        return cls(
            location=NodeLocation.from_pydantic(getattr(pyd_object, "location", None)),
            nodal_forces=NodeForces.from_pydantic(getattr(pyd_object, "nodal_forces", None)),
            support_id=int(getattr(pyd_object, "support_id", 0) or 0),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "location": self.location.to_dict(),
            "nodal_forces": self.nodal_forces.to_dict(),
            "support_id": self.support_id,
        }
