from __future__ import annotations

from typing import Dict, Any, List, Optional, Tuple, TYPE_CHECKING

from fers_core.results.nodes import NodeForces, SectionForce

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
        local_start_forces: Optional[NodeForces] = None,
        local_end_forces: Optional[NodeForces] = None,
        section_forces: Optional[List[SectionForce]] = None,
    ) -> None:
        self.start_node_forces = start_node_forces if start_node_forces is not None else NodeForces()
        self.end_node_forces = end_node_forces if end_node_forces is not None else NodeForces()
        self.maximums = maximums if maximums is not None else NodeForces()
        self.minimums = minimums if minimums is not None else NodeForces()
        self.local_start_forces = local_start_forces if local_start_forces is not None else NodeForces()
        self.local_end_forces = local_end_forces if local_end_forces is not None else NodeForces()
        self.section_forces: List[SectionForce] = section_forces if section_forces is not None else []

    @classmethod
    def from_pydantic(cls, model_object: Any) -> "MemberResult":
        raw_sf = getattr(model_object, "section_forces", None) or []
        section_forces = []
        for sf in raw_sf:
            if isinstance(sf, dict):
                section_forces.append(SectionForce.from_dict(sf))
            else:
                section_forces.append(SectionForce.from_pydantic(sf))
        return cls(
            start_node_forces=NodeForces.from_pydantic(getattr(model_object, "start_node_forces", None)),
            end_node_forces=NodeForces.from_pydantic(getattr(model_object, "end_node_forces", None)),
            maximums=NodeForces.from_pydantic(getattr(model_object, "maximums", None)),
            minimums=NodeForces.from_pydantic(getattr(model_object, "minimums", None)),
            local_start_forces=NodeForces.from_pydantic(getattr(model_object, "local_start_forces", None)),
            local_end_forces=NodeForces.from_pydantic(getattr(model_object, "local_end_forces", None)),
            section_forces=section_forces,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "start_node_forces": self.start_node_forces.to_dict(),
            "end_node_forces": self.end_node_forces.to_dict(),
            "maximums": self.maximums.to_dict(),
            "minimums": self.minimums.to_dict(),
            "local_start_forces": self.local_start_forces.to_dict(),
            "local_end_forces": self.local_end_forces.to_dict(),
            "section_forces": [sf.to_dict() for sf in self.section_forces],
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

        The diagram is drawn perpendicular to the member axis. When
        ``local_start_forces``/``local_end_forces`` are non-zero they are
        preferred over global node forces. When ``section_forces`` are
        available the diagram curves through those intermediate values.

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

        # Prefer local forces when they have been populated
        _local_nonzero = any(
            getattr(self.local_start_forces, c, 0) != 0 or getattr(self.local_end_forces, c, 0) != 0
            for c in ["fx", "fy", "fz", "mx", "my", "mz"]
        )
        if _local_nonzero:
            start_val = self.local_start_forces.get_value(diagram_type)
            end_val = self.local_end_forces.get_value(diagram_type)
        else:
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

        offset_axis = self._offset_axis(member, diagram_type)

        # Build t and value arrays — use section_forces when available
        if self.section_forces:
            t_vals = _np.array([0.0] + [sf.x_frac for sf in self.section_forces] + [1.0])
            v_vals = _np.array(
                [start_val] + [sf.forces.get_value(diagram_type) for sf in self.section_forces] + [end_val]
            )
        else:
            t_vals = _np.linspace(0.0, 1.0, num_points)
            v_vals = start_val * (1.0 - t_vals) + end_val * t_vals

        # Centreline and offset points
        centreline = (1.0 - t_vals)[:, None] * p0 + t_vals[:, None] * p1
        diagram_pts = centreline + (v_vals[:, None] * scale) * offset_axis[None, :]

        # Build a closed polygon: centreline → diagram → back
        polygon_pts = _np.vstack([centreline, diagram_pts[::-1]])
        n = len(polygon_pts)
        face = [n] + list(range(n))
        poly = _pv.PolyData(polygon_pts, faces=face)

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

    def plot_diagram(
        self,
        member: Any,
        diagram_type: str,
        ax: Any = None,
        label: Optional[str] = None,
        color_positive: str = "#ef4444",
        color_negative: str = "#3b82f6",
    ) -> Any:
        """Generate a 2D matplotlib force/moment diagram for this member.

        Args:
            member: The Member instance (for length).
            diagram_type: 'N', 'Vy', 'Vz', 'My', 'Mz', or 'T'.
            ax: Optional existing matplotlib Axes to plot into.
            label: Optional label for the member.
            color_positive: Fill color for positive values.
            color_negative: Fill color for negative values.

        Returns:
            The matplotlib Figure.
        """
        import matplotlib.pyplot as _plt

        length = member.calculate_length()

        _local_nonzero = any(
            getattr(self.local_start_forces, c, 0) != 0 or getattr(self.local_end_forces, c, 0) != 0
            for c in ["fx", "fy", "fz", "mx", "my", "mz"]
        )
        if _local_nonzero:
            start_val = self.local_start_forces.get_value(diagram_type)
            end_val = self.local_end_forces.get_value(diagram_type)
        else:
            start_val = self.start_node_forces.get_value(diagram_type)
            end_val = self.end_node_forces.get_value(diagram_type)

        if self.section_forces:
            t_vals = [0.0] + [sf.x_frac for sf in self.section_forces] + [1.0]
            v_vals = (
                [start_val] + [sf.forces.get_value(diagram_type) for sf in self.section_forces] + [end_val]
            )
        else:
            t_vals = [0.0, 1.0]
            v_vals = [start_val, end_val]

        x_vals = [t * length for t in t_vals]

        created_fig = ax is None
        if created_fig:
            fig, ax = _plt.subplots(figsize=(8, 3))
        else:
            fig = ax.figure

        ax.fill_between(
            x_vals,
            v_vals,
            where=[v >= 0 for v in v_vals],
            color=color_positive,
            alpha=0.4,
            interpolate=True,
        )
        ax.fill_between(
            x_vals,
            v_vals,
            where=[v < 0 for v in v_vals],
            color=color_negative,
            alpha=0.4,
            interpolate=True,
        )
        ax.plot(x_vals, v_vals, color="black", linewidth=1.5)
        ax.axhline(0, color="gray", linewidth=0.8, linestyle="--")

        for x, v in zip(x_vals, v_vals):
            if abs(v) > 1e-6:
                ax.annotate(
                    f"{v:.2f}",
                    (x, v),
                    textcoords="offset points",
                    xytext=(0, 5 if v >= 0 else -12),
                    fontsize=7,
                    ha="center",
                )

        ax.set_xlabel("Position along member (m)")
        ax.set_ylabel(diagram_type)
        ax.set_title(label or f"Member diagram — {diagram_type}")
        ax.grid(True, alpha=0.3)

        return fig
