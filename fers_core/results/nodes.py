from __future__ import annotations

from dataclasses import field
from typing import Dict, Any, List, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np
    import pyvista as pv

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
    def from_pydantic(cls, source) -> "NodeDisplacement":
        instance = cls()
        instance.dx = float(getattr(source, "dx", 0.0))
        instance.dy = float(getattr(source, "dy", 0.0))
        instance.dz = float(getattr(source, "dz", 0.0))
        instance.rx = float(getattr(source, "rx", 0.0))
        instance.ry = float(getattr(source, "ry", 0.0))
        instance.rz = float(getattr(source, "rz", 0.0))
        return instance

    def to_dict(self) -> Dict[str, float]:
        return {
            "dx": self.dx,
            "dy": self.dy,
            "dz": self.dz,
            "rx": self.rx,
            "ry": self.ry,
            "rz": self.rz,
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

    @classmethod
    def from_pydantic(cls, pyd_object: Any) -> "NodeForces":
        instance = cls()
        instance.fx = float(getattr(pyd_object, "fx", 0.0))
        instance.fy = float(getattr(pyd_object, "fy", 0.0))
        instance.fz = float(getattr(pyd_object, "fz", 0.0))
        instance.mx = float(getattr(pyd_object, "mx", 0.0))
        instance.my = float(getattr(pyd_object, "my", 0.0))
        instance.mz = float(getattr(pyd_object, "mz", 0.0))
        return instance

    def to_dict(self) -> Dict[str, float]:
        return {
            "fx": self.fx,
            "fy": self.fy,
            "fz": self.fz,
            "mx": self.mx,
            "my": self.my,
            "mz": self.mz,
        }

    def get_value(self, component: str) -> float:
        """Return a single force/moment component by name.

        Args:
            component: One of 'N'/'fx', 'Vy'/'fy', 'Vz'/'fz',
                       'T'/'mx', 'My'/'my', 'Mz'/'mz'.

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
        }
        key = component.lower()
        if key not in mapping:
            raise ValueError(f"Unknown force component '{component}'. Valid: {list(mapping.keys())}")
        return mapping[key]


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

    def to_dict(self) -> Dict[str, float]:
        return {"X": self.X, "Y": self.Y, "Z": self.Z}


class ReactionNodeResult:
    location: NodeLocation = field(default_factory=NodeLocation)
    nodal_forces: NodeForces = field(default_factory=NodeForces)
    support_id: int = 0

    @classmethod
    def from_pydantic(cls, pyd_object: Any) -> "ReactionNodeResult":
        instance = cls()
        instance.location = NodeLocation.from_pydantic(getattr(pyd_object, "location", None))
        instance.nodal_forces = NodeForces.from_pydantic(getattr(pyd_object, "nodal_forces", None))
        instance.support_id = int(getattr(pyd_object, "support_id", 0) or 0)
        return instance

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
