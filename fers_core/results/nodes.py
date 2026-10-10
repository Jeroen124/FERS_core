from __future__ import annotations

from typing import Dict, Any, List, Mapping, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np
    import pyvista as pv


def number(value: Any) -> float:
    """A result component as a float; the schema allows ``bw``/``warp`` to be null.

    Written as a test on None rather than ``value or 0.0``, which would turn -0.0
    into 0.0.
    """
    return 0.0 if value is None else float(value)


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
    warp: float = 0.0

    @classmethod
    def from_pydantic(cls, source) -> "NodeDisplacement":
        instance = cls()
        instance.dx = number(getattr(source, "dx", 0.0))
        instance.dy = number(getattr(source, "dy", 0.0))
        instance.dz = number(getattr(source, "dz", 0.0))
        instance.rx = number(getattr(source, "rx", 0.0))
        instance.ry = number(getattr(source, "ry", 0.0))
        instance.rz = number(getattr(source, "rz", 0.0))
        instance.warp = number(getattr(source, "warp", 0.0))
        return instance

    @classmethod
    def from_dict(cls, data: Optional[Mapping[str, Any]]) -> "NodeDisplacement":
        data = data or {}
        instance = cls()
        for name in ("dx", "dy", "dz", "rx", "ry", "rz", "warp"):
            setattr(instance, name, number(data.get(name)))
        return instance

    def to_dict(self) -> Dict[str, float]:
        return {
            "dx": self.dx,
            "dy": self.dy,
            "dz": self.dz,
            "rx": self.rx,
            "ry": self.ry,
            "rz": self.rz,
            "warp": self.warp,
        }

    def as_translation(self) -> "np.ndarray":
        """Return the translational displacement as a 3-element numpy array."""
        import numpy as _np

        return _np.array([self.dx, self.dy, self.dz], dtype=float)

    def as_rotation(self) -> "np.ndarray":
        """Return the rotational displacement as a 3-element numpy array."""
        import numpy as _np

        return _np.array([self.rx, self.ry, self.rz], dtype=float)

    def render_displaced_node(
        self,
        original_position: "np.ndarray",
        scale: float = 1.0,
        annotation_size: float = 1.0,
    ) -> List[Tuple["pv.PolyData", str]]:
        """Render the displaced node position as PyVista meshes.

        Args:
            original_position: Original [X, Y, Z] position of the node.
            scale: Displacement scale factor.
            annotation_size: Size reference for node markers.

        Returns:
            List of (mesh, color) tuples for rendering.
        """
        import pyvista as _pv

        displaced_pos = original_position + self.as_translation() * scale
        sphere = _pv.Sphere(
            center=tuple(displaced_pos),
            radius=0.2 * annotation_size,
        )
        return [(sphere, "red")]


class NodeForces:
    fx: float = 0.0
    fy: float = 0.0
    fz: float = 0.0
    mx: float = 0.0
    my: float = 0.0
    mz: float = 0.0
    bw: float = 0.0

    @classmethod
    def from_pydantic(cls, pyd_object: Any) -> "NodeForces":
        instance = cls()
        instance.fx = number(getattr(pyd_object, "fx", 0.0))
        instance.fy = number(getattr(pyd_object, "fy", 0.0))
        instance.fz = number(getattr(pyd_object, "fz", 0.0))
        instance.mx = number(getattr(pyd_object, "mx", 0.0))
        instance.my = number(getattr(pyd_object, "my", 0.0))
        instance.mz = number(getattr(pyd_object, "mz", 0.0))
        instance.bw = number(getattr(pyd_object, "bw", 0.0))
        return instance

    @classmethod
    def from_dict(cls, data: Optional[Mapping[str, Any]]) -> "NodeForces":
        data = data or {}
        instance = cls()
        for name in ("fx", "fy", "fz", "mx", "my", "mz", "bw"):
            setattr(instance, name, number(data.get(name)))
        return instance

    def to_dict(self) -> Dict[str, float]:
        return {
            "fx": self.fx,
            "fy": self.fy,
            "fz": self.fz,
            "mx": self.mx,
            "my": self.my,
            "mz": self.mz,
            "bw": self.bw,
        }

    def get_value(self, component: str) -> float:
        """Return a single force/moment component by name.

        Args:
            component: One of 'N'/'fx', 'Vy'/'fy', 'Vz'/'fz',
                       'T'/'mx', 'My'/'my', 'Mz'/'mz', 'bw'/'bimoment'.

        Returns:
            The scalar value for the requested component.
        """
        mapping = {
            "n": self.fx,
            "fx": self.fx,
            "vy": self.fy,
            "fy": self.fy,
            "vz": self.fz,
            "fz": self.fz,
            "t": self.mx,
            "mx": self.mx,
            "my": self.my,
            "mz": self.mz,
            "bw": self.bw,
            "bimoment": self.bw,
        }
        key = component.lower()
        if key not in mapping:
            raise ValueError(f"Unknown force component '{component}'. Valid: {list(mapping.keys())}")
        return mapping[key]


class SectionForce:
    x_frac: float = 0.0
    forces: "NodeForces" = None

    def __init__(self):
        self.x_frac = 0.0
        self.forces = NodeForces()

    @classmethod
    def from_pydantic(cls, source) -> "SectionForce":
        instance = cls()
        instance.x_frac = float(getattr(source, "x_frac", 0.0))
        forces_raw = getattr(source, "forces", None)
        instance.forces = NodeForces.from_pydantic(forces_raw) if forces_raw is not None else NodeForces()
        return instance

    @classmethod
    def from_dict(cls, d: dict) -> "SectionForce":
        instance = cls()
        instance.x_frac = float(d.get("x_frac", 0.0))
        forces_raw = d.get("forces", {})

        class _N:
            pass

        n = _N()
        for k, v in forces_raw.items():
            setattr(n, k, v)
        instance.forces = NodeForces.from_pydantic(n)
        return instance

    def to_dict(self) -> dict:
        return {"x_frac": self.x_frac, "forces": self.forces.to_dict()}


class NodeLocation:
    X: float = 0.0
    Y: float = 0.0
    Z: float = 0.0

    @classmethod
    def from_pydantic(cls, pyd_object: Any) -> "NodeLocation":
        instance = cls()
        instance.X = float(getattr(pyd_object, "X", 0.0))
        instance.Y = float(getattr(pyd_object, "Y", 0.0))
        instance.Z = float(getattr(pyd_object, "Z", 0.0))
        return instance

    @classmethod
    def from_dict(cls, data: Optional[Mapping[str, Any]]) -> "NodeLocation":
        data = data or {}
        instance = cls()
        instance.X, instance.Y, instance.Z = (number(data.get(axis)) for axis in ("X", "Y", "Z"))
        return instance

    def to_dict(self) -> Dict[str, float]:
        return {"X": self.X, "Y": self.Y, "Z": self.Z}


class ReactionNodeResult:
    location: NodeLocation
    nodal_forces: NodeForces
    support_id: int = 0

    # Real defaults: these were `field(default_factory=...)` on a class that is not a
    # dataclass, so a bare ReactionNodeResult() read back `dataclasses.Field` objects.
    def __init__(
        self,
        location: Optional[NodeLocation] = None,
        nodal_forces: Optional[NodeForces] = None,
        support_id: int = 0,
    ) -> None:
        self.location = location if location is not None else NodeLocation()
        self.nodal_forces = nodal_forces if nodal_forces is not None else NodeForces()
        self.support_id = support_id

    @classmethod
    def from_pydantic(cls, pyd_object: Any) -> "ReactionNodeResult":
        instance = cls()
        instance.location = NodeLocation.from_pydantic(getattr(pyd_object, "location", None))
        instance.nodal_forces = NodeForces.from_pydantic(getattr(pyd_object, "nodal_forces", None))
        instance.support_id = int(getattr(pyd_object, "support_id", 0) or 0)
        return instance

    @classmethod
    def from_dict(cls, data: Optional[Mapping[str, Any]]) -> "ReactionNodeResult":
        data = data or {}
        return cls(
            location=NodeLocation.from_dict(data.get("location")),
            nodal_forces=NodeForces.from_dict(data.get("nodal_forces")),
            support_id=int(data.get("support_id") or 0),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "location": self.location.to_dict(),
            "nodal_forces": self.nodal_forces.to_dict(),
            "support_id": self.support_id,
        }

    def render_reaction(
        self,
        position: "np.ndarray",
        max_force_magnitude: float,
        arrow_scale: float = 1.0,
        show_label: bool = False,
    ) -> List[Tuple["pv.PolyData", str]]:
        """Render reaction force arrows as PyVista meshes.

        Args:
            position: [X, Y, Z] position of the reaction node.
            max_force_magnitude: Maximum reaction force magnitude across all
                reaction nodes (used for relative scaling).
            arrow_scale: Base arrow length.
            show_label: Whether to include a text label (not rendered
                directly, returned as metadata).

        Returns:
            List of (mesh, color) tuples for rendering.
        """
        import numpy as _np
        import pyvista as _pv

        fv = _np.array(
            [self.nodal_forces.fx, self.nodal_forces.fy, self.nodal_forces.fz],
            dtype=float,
        )
        mag = float(_np.linalg.norm(fv))
        if mag <= 0.0 or max_force_magnitude <= 0.0:
            return []

        direction = fv / mag
        rel = mag / max_force_magnitude
        length = arrow_scale * max(rel, 0.1)
        arrow_vec = direction * length

        meshes: List[Tuple["_pv.PolyData", str]] = []
        arrow = _pv.Arrow(
            start=tuple(position),
            direction=tuple(arrow_vec),
            scale="auto",
        )
        meshes.append((arrow, "magenta"))
        return meshes
