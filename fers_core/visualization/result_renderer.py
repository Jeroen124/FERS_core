"""Result renderer for FERS finite element analysis results.

This module provides the ResultRenderer class for visualizing analysis results
including deformed shapes, stress contours, and internal force diagrams.
"""

from typing import TYPE_CHECKING, Optional, Tuple
import warnings
import numpy as np
import pyvista as pv

if TYPE_CHECKING:
    from ..fers.fers import FERS

# Suppress PyVista warnings for clean console output
warnings.filterwarnings("ignore", category=UserWarning, module="pyvista")
warnings.filterwarnings("ignore", message=".*Points is not a float type.*")

# Configure PyVista for Jupyter notebook support (optional)
try:
    pv.global_theme.trame.jupyter_extension_enabled = True
    pv.set_jupyter_backend("trame")
except (ImportError, Exception):
    # Trame not installed - jupyter functionality will be limited
    pass


class ResultRenderer:
    """Renderer for FERS finite element analysis results.

    This class provides methods for visualizing analysis results including
    deformed shapes, stress contours, and internal force diagrams.

    Attributes:
        model: The FERS model with analysis results
        plotter: PyVista plotter instance for rendering
        deformed_shape: Whether to render deformed shape
        deformed_scale: Scale factor for deformed shape
        color_map: Color map for contour plots
        scalar_bar: Whether to show scalar bar
        member_diagrams: Type of member diagram to display
        diagram_scale: Scale factor for diagrams
    """

    def __init__(self, model: "FERS") -> None:
        """Initialize the result renderer.

        Args:
            model: FERS finite element model with analysis results
        """
        self.model = model

        # Rendering settings
        self._deformed_shape: bool = False
        self._deformed_scale: float = 30.0
        self._color_map: Optional[str] = "jet"
        self._scalar_bar: bool = True
        self._scalar_bar_text_size: int = 24
        self._member_diagrams: Optional[str] = None  # Options: 'N', 'Vy', 'Vz', 'My', 'Mz', 'T'
        self._diagram_scale: float = 30.0
        self._annotation_size: Optional[float] = None

        # Create plotter
        self.plotter: pv.Plotter = pv.Plotter(off_screen=pv.OFF_SCREEN)
        self.plotter.set_background("white")

        # Set up view (only in interactive mode)
        if not pv.OFF_SCREEN:
            self.plotter.view_xy()
            self.plotter.show_axes()
            self.plotter.set_viewup((0, 1, 0))

        # Make X button behave like 'q' key
        self.plotter.iren.add_observer("ExitEvent", lambda obj, event: obj.TerminateApp())

    @property
    def annotation_size(self) -> float:
        """Get the annotation size, auto-calculating if not set."""
        if self._annotation_size is not None:
            return self._annotation_size

        # Auto-calculate based on model bounds
        if hasattr(self.model, "nodes") and len(self.model.nodes) > 0:
            x_coords = [node.X for node in self.model.nodes]
            y_coords = [node.Y for node in self.model.nodes]
            z_coords = [node.Z for node in self.model.nodes]

            x_range = max(x_coords) - min(x_coords) if x_coords else 1.0
            y_range = max(y_coords) - min(y_coords) if y_coords else 1.0
            z_range = max(z_coords) - min(z_coords) if z_coords else 1.0

            max_range = max(x_range, y_range, z_range, 1.0)
            return max_range * 0.05

        return 1.0

    @property
    def deformed_shape(self) -> bool:
        """Whether to render deformed shape."""
        return self._deformed_shape

    @deformed_shape.setter
    def deformed_shape(self, value: bool) -> None:
        self._deformed_shape = value

    @property
    def deformed_scale(self) -> float:
        """Scale factor for deformed shape."""
        return self._deformed_scale

    @deformed_scale.setter
    def deformed_scale(self, value: float) -> None:
        self._deformed_scale = value

    @property
    def color_map(self) -> Optional[str]:
        """Color map for contour plots."""
        return self._color_map

    @color_map.setter
    def color_map(self, value: str) -> None:
        self._color_map = value

    @property
    def scalar_bar(self) -> bool:
        """Whether to show scalar bar."""
        return self._scalar_bar

    @scalar_bar.setter
    def scalar_bar(self, value: bool) -> None:
        self._scalar_bar = value

    @property
    def member_diagrams(self) -> Optional[str]:
        """Type of member diagram to display."""
        return self._member_diagrams

    @member_diagrams.setter
    def member_diagrams(self, value: Optional[str]) -> None:
        """Set the type of member diagram to display.

        Args:
            value: Diagram type ('N', 'Vy', 'Vz', 'My', 'Mz', 'T') or None
        """
        valid_diagrams = [None, "N", "Vy", "Vz", "My", "Mz", "T"]
        if value not in valid_diagrams:
            raise ValueError(f"Invalid diagram type. Must be one of {valid_diagrams}")
        self._member_diagrams = value

    @property
    def diagram_scale(self) -> float:
        """Scale factor for diagrams."""
        return self._diagram_scale

    @diagram_scale.setter
    def diagram_scale(self, value: float) -> None:
        self._diagram_scale = value

    def update(self) -> None:
        """Update the visualization by clearing and re-rendering results."""
        # Clear the plotter
        self.plotter.clear()

        # Render undeformed shape in light color if showing deformed shape
        if self.deformed_shape:
            self._render_undeformed_model(color="lightgray", line_width=1)

        # Render members
        if hasattr(self.model, "members"):
            for member in self.model.members:
                self._render_member(member)

        # Render nodes
        if hasattr(self.model, "nodes"):
            for node in self.model.nodes:
                self._render_node(node)

        # Render member diagrams if specified
        if self.member_diagrams and hasattr(self.model, "members"):
            for member in self.model.members:
                self._render_member_diagram(member, self.member_diagrams)

        # Set up view for off-screen mode
        if pv.OFF_SCREEN:
            self.plotter.view_xy()
            self.plotter.show_axes()
            self.plotter.set_viewup((0, 1, 0))

    def _render_undeformed_model(self, color: str = "lightgray", line_width: int = 1) -> None:
        """Render the undeformed model.

        Args:
            color: Color for undeformed shape
            line_width: Line width for members
        """
        if hasattr(self.model, "members"):
            for member in self.model.members:
                line = pv.Line(
                    (member.start_node.X, member.start_node.Y, member.start_node.Z),
                    (member.end_node.X, member.end_node.Y, member.end_node.Z),
                )
                self.plotter.add_mesh(line, color=color, line_width=line_width)

    def _get_node_displacement(self, node) -> Tuple[float, float, float]:
        """Get node displacement values.

        Args:
            node: Node instance

        Returns:
            Tuple of (dx, dy, dz) displacements
        """
        # This is a placeholder - actual implementation depends on how
        # results are stored in your model
        # You'll need to adapt this to match your results structure
        if hasattr(node, "displacement"):
            disp = node.displacement
            return (disp.get("dx", 0.0), disp.get("dy", 0.0), disp.get("dz", 0.0))
        return (0.0, 0.0, 0.0)

    def _render_node(self, node) -> None:
        """Render a node with displacement.

        Args:
            node: Node instance to render
        """
        # Get coordinates
        x, y, z = node.X, node.Y, node.Z

        # Apply deformation if enabled
        if self.deformed_shape:
            dx, dy, dz = self._get_node_displacement(node)
            x += dx * self.deformed_scale
            y += dy * self.deformed_scale
            z += dz * self.deformed_scale

        # Render node
        sphere = pv.Sphere(center=(x, y, z), radius=0.2 * self.annotation_size)
        self.plotter.add_mesh(sphere, color="red")

    def _render_member(self, member) -> None:
        """Render a member with deformation.

        Args:
            member: Member instance to render
        """
        # Get start and end coordinates
        x1, y1, z1 = member.start_node.X, member.start_node.Y, member.start_node.Z
        x2, y2, z2 = member.end_node.X, member.end_node.Y, member.end_node.Z

        # Apply deformation if enabled
        if self.deformed_shape:
            dx1, dy1, dz1 = self._get_node_displacement(member.start_node)
            dx2, dy2, dz2 = self._get_node_displacement(member.end_node)

            x1 += dx1 * self.deformed_scale
            y1 += dy1 * self.deformed_scale
            z1 += dz1 * self.deformed_scale

            x2 += dx2 * self.deformed_scale
            y2 += dy2 * self.deformed_scale
            z2 += dz2 * self.deformed_scale

        # Render member
        line = pv.Line((x1, y1, z1), (x2, y2, z2))
        self.plotter.add_mesh(line, color="blue", line_width=3)

    def _render_member_diagram(self, member, diagram_type: str) -> None:
        """Render internal force diagram for a member.

        Args:
            member: Member instance
            diagram_type: Type of diagram ('N', 'Vy', 'Vz', 'My', 'Mz', 'T')
        """
        # This is a placeholder for diagram rendering
        # You'll need to implement this based on your results structure

        # Get member axis
        x1, y1, z1 = member.start_node.X, member.start_node.Y, member.start_node.Z
        x2, y2, z2 = member.end_node.X, member.end_node.Y, member.end_node.Z

        # Create points along member for diagram
        num_points = 10
        t_values = np.linspace(0, 1, num_points)

        diagram_points = []
        for t in t_values:
            # Interpolate along member
            x = x1 + t * (x2 - x1)
            y = y1 + t * (y2 - y1)
            z = z1 + t * (z2 - z1)

            # Get force/moment value at this location
            # This is a placeholder - implement based on your results
            force_value = self._get_member_force(member, diagram_type, t)

            # Offset point perpendicular to member
            # This is simplified - you may want to use member local axes
            y_offset = force_value * self.diagram_scale / 1000.0  # Scale appropriately

            diagram_points.append([x, y + y_offset, z])

        # Create polyline for diagram
        if len(diagram_points) > 1:
            polyline = pv.lines_from_points(np.array(diagram_points))
            self.plotter.add_mesh(polyline, color="red", line_width=2)

    def _get_member_force(self, member, force_type: str, position: float) -> float:
        """Get member internal force at a position.

        Args:
            member: Member instance
            force_type: Type of force ('N', 'Vy', 'Vz', 'My', 'Mz', 'T')
            position: Position along member (0 to 1)

        Returns:
            Force value
        """
        # This is a placeholder - implement based on your results structure
        # You'll need to access the actual analysis results from the model
        return 0.0

    def show(self, jupyter_backend: str = "trame", screenshot: Optional[str] = None) -> None:
        """Display the rendered results.

        Args:
            jupyter_backend: Backend to use in Jupyter notebooks
            screenshot: Path to save screenshot, if provided
        """
        self.update()

        if screenshot:
            self.plotter.screenshot(screenshot)

        return self.plotter.show(jupyter_backend=jupyter_backend)

    def screenshot(self, filename: str) -> None:
        """Save a screenshot of the current view.

        Args:
            filename: Path to save the screenshot
        """
        self.update()
        self.plotter.screenshot(filename)

    def close(self) -> None:
        """Close the plotter."""
        self.plotter.close()
