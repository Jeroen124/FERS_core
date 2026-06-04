from typing import Any, Dict, Optional


class WorkAxis:
    """A named construction axis defined by an origin point and a direction."""

    _work_axis_counter = 1

    def __init__(
        self,
        origin_x: float = 0.0,
        origin_y: float = 0.0,
        origin_z: float = 0.0,
        direction_x: float = 1.0,
        direction_y: float = 0.0,
        direction_z: float = 0.0,
        name: Optional[str] = None,
        id: Optional[int] = None,
    ) -> None:
        self.id = id or WorkAxis._work_axis_counter
        if id is None:
            WorkAxis._work_axis_counter += 1
        self.origin_x = float(origin_x)
        self.origin_y = float(origin_y)
        self.origin_z = float(origin_z)
        self.direction_x = float(direction_x)
        self.direction_y = float(direction_y)
        self.direction_z = float(direction_z)
        self.name = name

    @classmethod
    def reset_counter(cls) -> None:
        cls._work_axis_counter = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "origin_x": self.origin_x,
            "origin_y": self.origin_y,
            "origin_z": self.origin_z,
            "direction_x": self.direction_x,
            "direction_y": self.direction_y,
            "direction_z": self.direction_z,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkAxis":
        obj = cls(
            id=data.get("id"),
            name=data.get("name"),
            origin_x=data.get("origin_x", 0.0),
            origin_y=data.get("origin_y", 0.0),
            origin_z=data.get("origin_z", 0.0),
            direction_x=data.get("direction_x", 1.0),
            direction_y=data.get("direction_y", 0.0),
            direction_z=data.get("direction_z", 0.0),
        )
        if obj.id is not None and obj.id >= cls._work_axis_counter:
            cls._work_axis_counter = obj.id + 1
        return obj
