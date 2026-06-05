from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Union


class PlateBehavior(Enum):
    SHELL = "Shell"
    MEMBRANE = "Membrane"


class PlateElementShape(Enum):
    AUTO = "Auto"
    TRIANGLE = "Triangle"
    QUAD = "Quad"


class PlateTheory(Enum):
    AUTO = "Auto"
    MINDLIN = "Mindlin"
    KIRCHHOFF = "Kirchhoff"


class PlaneState(Enum):
    PLANE_STRESS = "PlaneStress"
    PLANE_STRAIN = "PlaneStrain"


class PlateMeshMethod(Enum):
    AUTO = "Auto"
    STRUCTURED = "Structured"
    UNSTRUCTURED = "Unstructured"


def _normalize_enum(enum_cls, value):
    """Coerce a string/enum into an enum member (or pass through None)."""
    if value is None or isinstance(value, enum_cls):
        return value
    s = str(value).strip().lower()
    for member in enum_cls:
        if member.value.lower() == s or member.name.lower() == s:
            return member
    raise ValueError(f"Unknown {enum_cls.__name__}: {value!r}")


def normalize_plate_behavior(
    value: Union[PlateBehavior, str, None],
) -> Optional[PlateBehavior]:
    if value is None or isinstance(value, PlateBehavior):
        return value
    s = str(value).strip().lower()
    for member in PlateBehavior:
        if member.value.lower() == s or member.name.lower() == s:
            return member
    raise ValueError(f"Unknown plate behavior: {value!r}")


def normalize_element_shape(
    value: Union[PlateElementShape, str, None],
) -> Optional[PlateElementShape]:
    if value is None or isinstance(value, PlateElementShape):
        return value
    s = str(value).strip().lower()
    for member in PlateElementShape:
        if member.value.lower() == s or member.name.lower() == s:
            return member
    raise ValueError(f"Unknown plate element shape: {value!r}")


class PlateStiffnessModifiers:
    """Optional per-plate stiffness scale factors (bending / membrane / shear)."""

    def __init__(
        self,
        bending: Optional[float] = None,
        membrane: Optional[float] = None,
        shear: Optional[float] = None,
    ) -> None:
        self.bending = bending
        self.membrane = membrane
        self.shear = shear

    def to_dict(self) -> Dict[str, Any]:
        return {"bending": self.bending, "membrane": self.membrane, "shear": self.shear}

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> Optional["PlateStiffnessModifiers"]:
        if data is None:
            return None
        return cls(
            bending=data.get("bending"),
            membrane=data.get("membrane"),
            shear=data.get("shear"),
        )


class PlateMeshDivisions:
    """Division counts for a structured (u, v) mesh."""

    def __init__(self, u: int, v: int) -> None:
        self.u = u
        self.v = v

    def to_dict(self) -> Dict[str, Any]:
        return {"u": self.u, "v": self.v}

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> Optional["PlateMeshDivisions"]:
        if data is None:
            return None
        return cls(u=data["u"], v=data["v"])


class PlateMeshSettings:
    """Meshing controls for a PlateSurface."""

    def __init__(
        self,
        element_shape: Union[PlateElementShape, str, None] = None,
        target_size: Optional[float] = None,
        method: Union[PlateMeshMethod, str, None] = None,
        divisions: Optional[PlateMeshDivisions] = None,
    ) -> None:
        self.element_shape = normalize_element_shape(element_shape)
        self.target_size = float(target_size) if target_size is not None else None
        self.method = _normalize_enum(PlateMeshMethod, method)
        self.divisions = divisions

    def to_dict(self) -> Dict[str, Any]:
        # Omit `element_shape` when unset: the solver's field is a non-nullable
        # enum with a serde default and rejects an explicit null.
        data: Dict[str, Any] = {"target_size": self.target_size}
        if self.element_shape is not None:
            data["element_shape"] = self.element_shape.value
        if self.method is not None:
            data["method"] = self.method.value
        if self.divisions is not None:
            data["divisions"] = self.divisions.to_dict()
        return data

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> Optional["PlateMeshSettings"]:
        if data is None:
            return None
        return cls(
            element_shape=data.get("element_shape"),
            target_size=data.get("target_size"),
            method=data.get("method"),
            divisions=PlateMeshDivisions.from_dict(data.get("divisions")),
        )


class PlateOpening:
    """A hole in a PlateSurface, defined by a boundary of node ids."""

    _plate_opening_counter = 1

    def __init__(
        self,
        boundary_node_ids: Optional[List[int]] = None,
        id: Optional[int] = None,
    ) -> None:
        self.id = id or PlateOpening._plate_opening_counter
        if id is None:
            PlateOpening._plate_opening_counter += 1
        self.boundary_node_ids = list(boundary_node_ids) if boundary_node_ids is not None else None

    @classmethod
    def reset_counter(cls) -> None:
        cls._plate_opening_counter = 1

    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "boundary_node_ids": self.boundary_node_ids}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlateOpening":
        obj = cls(id=data.get("id"), boundary_node_ids=data.get("boundary_node_ids"))
        if obj.id is not None and obj.id >= cls._plate_opening_counter:
            cls._plate_opening_counter = obj.id + 1
        return obj
