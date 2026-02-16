"""Model renderer for FERS finite element models.

This module provides the ModelRenderer class for visualizing structural models
using PyVista, including nodes, members, supports, and loads.
"""

from typing import TYPE_CHECKING, Optional, List, Callable
import warnings
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


class ModelRenderer:
    """Renderer for FERS finite element models.

    This class provides methods for visualizing structural models including
    nodes, members, supports, and applied loads using PyVista.

    Attributes:
        model: The FERS model to be rendered
        plotter: PyVista plotter instance for rendering
        annotation_size: Size for annotations and support symbols
        render_nodes: Whether to render node markers
        render_supports: Whether to render support symbols
        render_loads: Whether to render load indicators
        labels: Whether to show labels for nodes and members
        theme: Color theme for rendering
    """

    def __init__(self, model: "FERS") -> None:
        """Initialize the model renderer.

        Args:
            model: FERS finite element model to render
        """
        self.model = model

        # Rendering settings
        self._annotation_size: Optional[float] = None  # Auto-calculate if None
        self._annotation_size_manual: bool = False
        self._render_nodes: bool = True
        self._render_supports: bool = True
        self._render_loads: bool = True
        self._labels: bool = True
        self.theme: str = "default"

        # Callback list for post-update customization
        self.post_update_callbacks: List[Callable[[pv.Plotter], None]] = []

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
        """Get the annotation size, auto-calculating if not manually set."""
        if self._annotation_size_manual and self._annotation_size is not None:
            return self._annotation_size

        # Auto-calculate based on model bounds
        if hasattr(self.model, "nodes") and len(self.model.nodes) > 0:
            # Get bounding box of all nodes
            x_coords = [node.X for node in self.model.nodes]
            y_coords = [node.Y for node in self.model.nodes]
            z_coords = [node.Z for node in self.model.nodes]

            x_range = max(x_coords) - min(x_coords) if x_coords else 1.0
            y_range = max(y_coords) - min(y_coords) if y_coords else 1.0
            z_range = max(z_coords) - min(z_coords) if z_coords else 1.0

            # Use 5% of the largest dimension
            max_range = max(x_range, y_range, z_range, 1.0)
            return max_range * 0.05

        return 1.0  # Default if no nodes

    @annotation_size.setter
    def annotation_size(self, value: float) -> None:
        """Set annotation size manually."""
        self._annotation_size = value
        self._annotation_size_manual = True

    @property
    def render_nodes(self) -> bool:
        """Whether to render node markers."""
        return self._render_nodes

    @render_nodes.setter
    def render_nodes(self, value: bool) -> None:
        self._render_nodes = value

    @property
    def render_supports(self) -> bool:
        """Whether to render support symbols."""
        return self._render_supports

    @render_supports.setter
    def render_supports(self, value: bool) -> None:
        self._render_supports = value

    @property
    def render_loads(self) -> bool:
        """Whether to render load indicators."""
        return self._render_loads

    @render_loads.setter
    def render_loads(self, value: bool) -> None:
        self._render_loads = value

    @property
    def labels(self) -> bool:
        """Whether to show labels."""
        return self._labels

    @labels.setter
    def labels(self, value: bool) -> None:
        self._labels = value

    def update(self) -> None:
        """Update the visualization by clearing and re-rendering the model."""
        # Clear the plotter
        self.plotter.clear()

        # Render the model components
        if hasattr(self.model, "members"):
            for member in self.model.members:
                self._render_member(member)

        if self.render_nodes and hasattr(self.model, "nodes"):
            for node in self.model.nodes:
                self._render_node(node)

        if self.render_supports and hasattr(self.model, "nodes"):
            for node in self.model.nodes:
                if node.nodal_support is not None:
                    self._render_node_support(node)

        # Execute post-update callbacks
        for callback in self.post_update_callbacks:
            callback(self.plotter)

        # Set up view for off-screen mode
        if pv.OFF_SCREEN:
            self.plotter.view_xy()
            self.plotter.show_axes()
            self.plotter.set_viewup((0, 1, 0))

    def _render_node(self, node) -> None:
        """Render a single node.

        Args:
            node: Node instance to render
        """
        # Check if node has a render method
        if hasattr(node, "render"):
            meshes = node.render(annotation_size=self.annotation_size, theme=self.theme)
            if meshes:
                for mesh, color in meshes:
                    self.plotter.add_mesh(mesh, color=color)
        else:
            # Default node rendering: small sphere
            sphere = pv.Sphere(center=(node.X, node.Y, node.Z), radius=0.2 * self.annotation_size)
            self.plotter.add_mesh(sphere, color="black")

        # Add label if enabled
        if self.labels and hasattr(node, "id"):
            self.plotter.add_point_labels(
                [(node.X, node.Y, node.Z)], [str(node.id)], font_size=12, point_size=1, text_color="black"
            )

    def _render_member(self, member) -> None:
        """Render a single member.

        Args:
            member: Member instance to render
        """
        # Check if member has a render method
        if hasattr(member, "render"):
            meshes = member.render(theme=self.theme)
            if meshes:
                for mesh, color, line_width in meshes:
                    self.plotter.add_mesh(mesh, color=color, line_width=line_width)
        else:
            # Default member rendering: line between nodes
            line = pv.Line(
                (member.start_node.X, member.start_node.Y, member.start_node.Z),
                (member.end_node.X, member.end_node.Y, member.end_node.Z),
            )
            self.plotter.add_mesh(line, color="black", line_width=2)

        # Add label if enabled
        if self.labels and hasattr(member, "id"):
            # Label at midpoint of member
            mid_x = (member.start_node.X + member.end_node.X) / 2
            mid_y = (member.start_node.Y + member.end_node.Y) / 2
            mid_z = (member.start_node.Z + member.end_node.Z) / 2
            self.plotter.add_point_labels(
                [(mid_x, mid_y, mid_z)], [str(member.id)], font_size=12, point_size=1, text_color="blue"
            )

    def _render_node_support(self, node) -> None:
        """Render support symbol for a node.

        Args:
            node: Node instance with nodal_support
        """
        if node.nodal_support is None:
            return

        support = node.nodal_support
        color = "green"
        size = self.annotation_size

        # Check for fixed support (all DOFs restrained)
        if all([support.Tx, support.Ty, support.Tz, support.Rx, support.Ry, support.Rz]):
            # Fixed support: cube
            cube = pv.Cube(
                center=(node.X, node.Y - size, node.Z),
                x_length=size * 2,
                y_length=size * 2,
                z_length=size * 2,
            )
            self.plotter.add_mesh(cube, color=color)

        # Check for pinned support (translations only)
        elif all([support.Tx, support.Ty, support.Tz]) and not any([support.Rx, support.Ry, support.Rz]):
            # Pinned support: cone
            cone = pv.Cone(
                center=(node.X, node.Y - size, node.Z), direction=(0, 1, 0), height=size * 2, radius=size * 2
            )
            self.plotter.add_mesh(cone, color=color)

        # Other support conditions: render individual restraints
        else:
            # Translation X
            if support.Tx:
                line = pv.Line((node.X - size, node.Y, node.Z), (node.X + size, node.Y, node.Z))
                self.plotter.add_mesh(line, color=color, line_width=3)

                # Cones at ends
                cone1 = pv.Cone(
                    center=(node.X - size, node.Y, node.Z),
                    direction=(1, 0, 0),
                    height=size * 0.6,
                    radius=size * 0.3,
                )
                cone2 = pv.Cone(
                    center=(node.X + size, node.Y, node.Z),
                    direction=(-1, 0, 0),
                    height=size * 0.6,
                    radius=size * 0.3,
                )
                self.plotter.add_mesh(cone1, color=color)
                self.plotter.add_mesh(cone2, color=color)

            # Translation Y
            if support.Ty:
                line = pv.Line((node.X, node.Y - size, node.Z), (node.X, node.Y + size, node.Z))
                self.plotter.add_mesh(line, color=color, line_width=3)

                cone1 = pv.Cone(
                    center=(node.X, node.Y - size, node.Z),
                    direction=(0, 1, 0),
                    height=size * 0.6,
                    radius=size * 0.3,
                )
                cone2 = pv.Cone(
                    center=(node.X, node.Y + size, node.Z),
                    direction=(0, -1, 0),
                    height=size * 0.6,
                    radius=size * 0.3,
                )
                self.plotter.add_mesh(cone1, color=color)
                self.plotter.add_mesh(cone2, color=color)

            # Translation Z
            if support.Tz:
                line = pv.Line((node.X, node.Y, node.Z - size), (node.X, node.Y, node.Z + size))
                self.plotter.add_mesh(line, color=color, line_width=3)

                cone1 = pv.Cone(
                    center=(node.X, node.Y, node.Z - size),
                    direction=(0, 0, 1),
                    height=size * 0.6,
                    radius=size * 0.3,
                )
                cone2 = pv.Cone(
                    center=(node.X, node.Y, node.Z + size),
                    direction=(0, 0, -1),
                    height=size * 0.6,
                    radius=size * 0.3,
                )
                self.plotter.add_mesh(cone1, color=color)
                self.plotter.add_mesh(cone2, color=color)

    def show(self, jupyter_backend: str = "trame", screenshot: Optional[str] = None) -> None:
        """Display the rendered model.

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
