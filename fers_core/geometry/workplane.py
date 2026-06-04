from typing import Any, Dict, Optional


class WorkPlane:
    """A named construction plane defined by an origin point and a normal vector."""

    _work_plane_counter = 1

    def __init__(
        self,
        origin_x: float = 0.0,
        origin_y: float = 0.0,
        origin_z: float = 0.0,
        normal_x: float = 0.0,
        normal_y: float = 0.0,
        normal_z: float = 1.0,
        name: Optional[str] = None,
        id: Optional[int] = None,
    ) -> None:
        self.id = id or WorkPlane._work_plane_counter
        if id is None:
            WorkPlane._work_plane_counter += 1
        self.origin_x = float(origin_x)
        self.origin_y = float(origin_y)
        self.origin_z = float(origin_z)
        self.normal_x = float(normal_x)
        self.normal_y = float(normal_y)
        self.normal_z = float(normal_z)
        self.name = name

    @classmethod
    def reset_counter(cls) -> None:
        cls._work_plane_counter = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "origin_x": self.origin_x,
            "origin_y": self.origin_y,
            "origin_z": self.origin_z,
            "normal_x": self.normal_x,
            "normal_y": self.normal_y,
            "normal_z": self.normal_z,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkPlane":
        obj = cls(
            id=data.get("id"),
            name=data.get("name"),
            origin_x=data.get("origin_x", 0.0),
            origin_y=data.get("origin_y", 0.0),
            origin_z=data.get("origin_z", 0.0),
            normal_x=data.get("normal_x", 0.0),
            normal_y=data.get("normal_y", 0.0),
            normal_z=data.get("normal_z", 1.0),
        )
        if obj.id is not None and obj.id >= cls._work_plane_counter:
            cls._work_plane_counter = obj.id + 1
        return obj
