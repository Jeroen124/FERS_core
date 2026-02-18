from __future__ import annotations

from typing import Dict, Any, List, Optional, Tuple, TYPE_CHECKING

from fers_core.results.nodes import NodeForces

if TYPE_CHECKING:
    import numpy as np
    import pyvista as pv


class MemberResult:
    def __init__(
        self,
        start_node_forces: Optional[NodeForces] = None,
        end_node_forces: Optional[NodeForces] = None,
        maximums: Optional[NodeForces] = None,
        minimums: Optional[NodeForces] = None,
    ) -> None:
        self.start_node_forces = start_node_forces if start_node_forces is not None else NodeForces()
        self.end_node_forces = end_node_forces if end_node_forces is not None else NodeForces()
        self.maximums = maximums if maximums is not None else NodeForces()
        self.minimums = minimums if minimums is not None else NodeForces()

    @classmethod
    def from_pydantic(cls, model_object: Any) -> "MemberResult":
        return cls(
            start_node_forces=NodeForces.from_pydantic(getattr(model_object, "start_node_forces", None)),
            end_node_forces=NodeForces.from_pydantic(getattr(model_object, "end_node_forces", None)),
            maximums=NodeForces.from_pydantic(getattr(model_object, "maximums", None)),
            minimums=NodeForces.from_pydantic(getattr(model_object, "minimums", None)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "start_node_forces": self.start_node_forces.to_dict(),
            "end_node_forces": self.end_node_forces.to_dict(),
            "maximums": self.maximums.to_dict(),
            "minimums": self.minimums.to_dict(),
        }

    # ------------------------------------------------------------------
    # Rendering helpers — each returns a list of (mesh, color, line_width)
    # so the ResultRenderer can add them to a plotter without knowledge
    # of the internal result layout.
    # ------------------------------------------------------------------

    def render_deformed_shape(
        self,
        member: Any,
        disp_start: "np.ndarray",
        rot_start: "np.ndarray",
        disp_end: "np.ndarray",
        rot_end: "np.ndarray",
        scale: float = 1.0,
        num_points: int = 20,
    ) -> List[Tuple["pv.PolyData", str, int]]:
        """Render the deformed member centreline as a PyVista polyline.

        Uses Euler–Bernoulli cubic Hermite interpolation via
        :func:`~fers_core.fers.deformation_utils.centerline_path_points`.

        Args:
            member: The :class:`~fers_core.members.member.Member` instance.
            disp_start: Global translational displacement [dx, dy, dz] at start node.
            rot_start: Global rotational displacement [rx, ry, rz] at start node.
            disp_end: Global translational displacement [dx, dy, dz] at end node.
            rot_end: Global rotational displacement [rx, ry, rz] at end node.
            scale: Displacement scale factor.
            num_points: Number of interpolation points along the centreline.

        Returns:
            List of ``(mesh, color, line_width)`` tuples.
        """
        import numpy as _np
        import pyvista as _pv

        from fers_core.fers.deformation_utils import centerline_path_points

        original_curve, deformed_curve = centerline_path_points(
            member,
            disp_start,
            rot_start,
            disp_end,
            rot_end,
            num_points,
            scale,
        )

        # Smooth the deformed curve with a spline
        spline_pts = _np.ascontiguousarray(
            _pv.Spline(deformed_curve, max(num_points * 2, 2 * num_points + 1)).points,
            dtype=float,
        )
        spline_pts[0] = deformed_curve[0]
        spline_pts[-1] = deformed_curve[-1]

        meshes: List[Tuple[_pv.PolyData, str, int]] = []
        meshes.append((_pv.lines_from_points(original_curve), "blue", 2))
        meshes.append((_pv.lines_from_points(spline_pts), "red", 2))
        return meshes

    def render_diagram(
        self,
        member: Any,
        diagram_type: str,
        scale: float = 1.0,
        num_points: int = 20,
    ) -> List[Tuple["pv.PolyData", str, int]]:
        """Render an internal-force diagram for the member.

        The diagram is drawn perpendicular to the member axis using
        linear interpolation between start and end node forces.

        Args:
            member: The :class:`~fers_core.members.member.Member` instance.
            diagram_type: Force/moment component — ``'N'``, ``'Vy'``, ``'Vz'``,
                ``'My'``, ``'Mz'``, or ``'T'``.
            scale: Visual scale factor for the diagram offset.
            num_points: Number of points along the member for the diagram.

        Returns:
            List of ``(mesh, color, line_width)`` tuples.
        """
        import numpy as _np
        import pyvista as _pv

        start_val = self.start_node_forces.get_value(diagram_type)
        end_val = self.end_node_forces.get_value(diagram_type)

        p0 = _np.array(
            [member.start_node.X, member.start_node.Y, member.start_node.Z],
            dtype=float,
        )
        p1 = _np.array(
            [member.end_node.X, member.end_node.Y, member.end_node.Z],
            dtype=float,
        )

        # Choose offset axis based on diagram type
        offset_axis = self._offset_axis(member, diagram_type)

        t = _np.linspace(0.0, 1.0, num_points)
        values = start_val * (1.0 - t) + end_val * t

        # Centreline and offset points
        centreline = (1.0 - t)[:, None] * p0 + t[:, None] * p1
        diagram_pts = centreline + (values[:, None] * scale) * offset_axis[None, :]

        # Build a closed polygon: centreline → diagram → back
        polygon_pts = _np.vstack([centreline, diagram_pts[::-1]])
        n = len(polygon_pts)
        face = [n] + list(range(n))
        poly = _pv.PolyData(polygon_pts, faces=face)

        # Also draw just the diagram line for clarity
        diagram_line = _pv.lines_from_points(diagram_pts)

        meshes: List[Tuple[_pv.PolyData, str, int]] = []
        meshes.append((poly, "lightsalmon", 1))
        meshes.append((diagram_line, "red", 2))
        return meshes

    @staticmethod
    def _offset_axis(member: Any, component: str) -> "np.ndarray":
        """Return the local axis to use for diagram offset.

        Maps the force/moment component to an appropriate perpendicular
        direction in the member's local coordinate system.
        """
        import numpy as _np

        lx, ly, lz = member.local_coordinate_system()
        key = component.lower()
        if key in ("my", "m_y"):
            return _np.asarray(ly, dtype=float)
        if key in ("mz", "m_z"):
            return _np.asarray(lz, dtype=float)
        if key in ("mx", "m_x", "t"):
            return _np.asarray(lx, dtype=float)
        if key in ("vy", "fy"):
            return _np.asarray(ly, dtype=float)
        if key in ("vz", "fz"):
            return _np.asarray(lz, dtype=float)
        if key in ("n", "fx"):
            return _np.asarray(ly, dtype=float)
        return _np.asarray(ly, dtype=float)
