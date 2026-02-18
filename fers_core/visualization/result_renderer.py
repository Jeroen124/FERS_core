"""Result renderer for FERS finite element analysis results.

This module provides the :class:`ResultRenderer` class for visualising
analysis results — deformed shapes, internal-force diagrams, and reaction
arrows — using PyVista.

The renderer follows the same *"each class knows how to display itself"*
pattern as :class:`ModelRenderer`: it looks up result objects (e.g.
:class:`~fers_core.results.nodes.NodeDisplacement`,
:class:`~fers_core.results.member.MemberResult`,
:class:`~fers_core.results.nodes.ReactionNodeResult`) and delegates
rendering to their own ``render_*`` methods.
"""

from typing import TYPE_CHECKING, Optional, List
import warnings
import numpy as np
import pyvista as pv

if TYPE_CHECKING:
    from ..fers.fers import FERS
    from ..results.singleresults import SingleResults

# Suppress PyVista warnings for clean console output
warnings.filterwarnings("ignore", category=UserWarning, module="pyvista")
warnings.filterwarnings("ignore", message=".*Points is not a float type.*")

# Configure PyVista for Jupyter notebook support (optional)
try:
    pv.global_theme.trame.jupyter_extension_enabled = True
    pv.set_jupyter_backend("trame")
except (ImportError, Exception):
    pass


class ResultRenderer:
    """Renderer for FERS finite element analysis results.

    After running an analysis the model's
    :pyattr:`~fers_core.fers.fers.FERS.resultsbundle` contains one
    :class:`~fers_core.results.singleresults.SingleResults` per load case /
    combination.  The renderer selects one of those and delegates rendering
    to the result-data classes themselves.

    Attributes:
        model: The FERS model **with** analysis results.
        plotter: PyVista plotter instance.
        active_loadcase: Name of the active load-case to render (mutually
            exclusive with ``active_loadcombination``).
        active_loadcombination: Name of the active load-combination to
            render.
        deformed_shape: Whether to render the deformed shape.
        deformed_scale: Scale factor for deformations.
        member_diagrams: Which internal-force diagram to show
            (``'N'``, ``'Vy'``, ``'Vz'``, ``'My'``, ``'Mz'``, ``'T'``,
            or ``None``).
        diagram_scale: Scale factor for diagrams.
        show_reactions: Whether to draw reaction-force arrows.
        show_undeformed: Whether to ghost-draw the undeformed model.
    """

    # Valid diagram types
    VALID_DIAGRAMS: List[Optional[str]] = [None, "N", "Vy", "Vz", "My", "Mz", "T"]

    def __init__(self, model: "FERS") -> None:
        self.model = model

        # --- result selection ---
        self._active_loadcase: Optional[str] = None
        self._active_loadcombination: Optional[str] = None

        # --- rendering options ---
        self._deformed_shape: bool = True
        self._deformed_scale: float = 30.0
        self._member_diagrams: Optional[str] = None
        self._diagram_scale: float = 30.0
        self._show_reactions: bool = True
        self._show_undeformed: bool = True
        self._show_nodes: bool = True
        self._annotation_size: Optional[float] = None
        self._color_map: Optional[str] = "jet"
        self._scalar_bar: bool = True
        self._num_points: int = 20

        # --- plotter ---
        self.plotter: pv.Plotter = pv.Plotter(off_screen=pv.OFF_SCREEN)
        self.plotter.set_background("white")

        if not pv.OFF_SCREEN:
            self.plotter.view_xy()
            self.plotter.show_axes()
            self.plotter.set_viewup((0, 1, 0))

        self.plotter.iren.add_observer("ExitEvent", lambda obj, event: obj.TerminateApp())

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def annotation_size(self) -> float:
        """Auto-calculated annotation size (fraction of model extent)."""
        if self._annotation_size is not None:
            return self._annotation_size
        nodes = self.model.nodes if hasattr(self.model, "nodes") else []
        if not nodes:
            return 1.0
        xs = [n.X for n in nodes]
        ys = [n.Y for n in nodes]
        zs = [n.Z for n in nodes]
        max_range = max(
            max(xs) - min(xs),
            max(ys) - min(ys),
            max(zs) - min(zs),
            1.0,
        )
        return max_range * 0.05

    @annotation_size.setter
    def annotation_size(self, value: float) -> None:
        self._annotation_size = value

    # --- active result selection ---

    @property
    def active_loadcase(self) -> Optional[str]:
        """Name of the active load case to render."""
        return self._active_loadcase

    @active_loadcase.setter
    def active_loadcase(self, value: Optional[str]) -> None:
        self._active_loadcase = value
        if value is not None:
            self._active_loadcombination = None

    @property
    def active_loadcombination(self) -> Optional[str]:
        """Name of the active load combination to render."""
        return self._active_loadcombination

    @active_loadcombination.setter
    def active_loadcombination(self, value: Optional[str]) -> None:
        self._active_loadcombination = value
        if value is not None:
            self._active_loadcase = None

    # --- toggles ---

    @property
    def deformed_shape(self) -> bool:
        return self._deformed_shape

    @deformed_shape.setter
    def deformed_shape(self, value: bool) -> None:
        self._deformed_shape = value

    @property
    def deformed_scale(self) -> float:
        return self._deformed_scale

    @deformed_scale.setter
    def deformed_scale(self, value: float) -> None:
        self._deformed_scale = value

    @property
    def member_diagrams(self) -> Optional[str]:
        return self._member_diagrams

    @member_diagrams.setter
    def member_diagrams(self, value: Optional[str]) -> None:
        if value not in self.VALID_DIAGRAMS:
            raise ValueError(f"Invalid diagram type '{value}'. Must be one of {self.VALID_DIAGRAMS}")
        self._member_diagrams = value

    @property
    def diagram_scale(self) -> float:
        return self._diagram_scale

    @diagram_scale.setter
    def diagram_scale(self, value: float) -> None:
        self._diagram_scale = value

    @property
    def show_reactions(self) -> bool:
        return self._show_reactions

    @show_reactions.setter
    def show_reactions(self, value: bool) -> None:
        self._show_reactions = value

    @property
    def show_undeformed(self) -> bool:
        return self._show_undeformed

    @show_undeformed.setter
    def show_undeformed(self, value: bool) -> None:
        self._show_undeformed = value

    @property
    def show_nodes(self) -> bool:
        return self._show_nodes

    @show_nodes.setter
    def show_nodes(self, value: bool) -> None:
        self._show_nodes = value

    @property
    def color_map(self) -> Optional[str]:
        return self._color_map

    @color_map.setter
    def color_map(self, value: Optional[str]) -> None:
        self._color_map = value

    @property
    def scalar_bar(self) -> bool:
        return self._scalar_bar

    @scalar_bar.setter
    def scalar_bar(self, value: bool) -> None:
        self._scalar_bar = value

    @property
    def num_points(self) -> int:
        """Number of interpolation points for curves."""
        return self._num_points

    @num_points.setter
    def num_points(self, value: int) -> None:
        self._num_points = max(2, int(value))

    # ------------------------------------------------------------------
    # Result look-up
    # ------------------------------------------------------------------

    def _get_active_results(self) -> Optional["SingleResults"]:
        """Return the :class:`SingleResults` currently selected.

        Resolution order:
        1. ``active_loadcase``
        2. ``active_loadcombination``
        3. First available loadcase in the bundle.
        """
        bundle = getattr(self.model, "resultsbundle", None)
        if bundle is None:
            return None

        if self._active_loadcase and hasattr(bundle, "loadcases"):
            return bundle.loadcases.get(self._active_loadcase)

        if self._active_loadcombination and hasattr(bundle, "loadcombinations"):
            return bundle.loadcombinations.get(self._active_loadcombination)

        # Fallback: first loadcase
        if hasattr(bundle, "loadcases") and bundle.loadcases:
            first_key = next(iter(bundle.loadcases))
            return bundle.loadcases[first_key]

        return None

    # ------------------------------------------------------------------
    # Main update
    # ------------------------------------------------------------------

    def update(self) -> None:  # noqa: C901
        """Clear the plotter and re-render everything."""
        self.plotter.clear()

        results = self._get_active_results()
        members = self.model.members if hasattr(self.model, "members") else []
        nodes = self.model.nodes if hasattr(self.model, "nodes") else []

        # ---- undeformed ghost model ----
        if self.show_undeformed:
            self._render_undeformed_model(members)

        # ---- build displacement lookup ----
        node_displacements: dict[int, tuple[np.ndarray, np.ndarray]] = {}
        if results is not None and self.deformed_shape:
            disp_nodes = getattr(results, "displacement_nodes", {}) or {}
            for nid_str, disp in disp_nodes.items():
                nid = int(nid_str)
                if disp is not None:
                    node_displacements[nid] = (
                        disp.as_translation(),
                        disp.as_rotation(),
                    )

        # ---- deformed members ----
        if self.deformed_shape and node_displacements:
            self._render_deformed_members(members, node_displacements, results)

        # ---- deformed/original nodes ----
        if self.show_nodes:
            self._render_nodes(nodes, node_displacements, results)

        # ---- internal-force diagrams ----
        if self.member_diagrams and results is not None:
            self._render_diagrams(members, results)

        # ---- reactions ----
        if self.show_reactions and results is not None:
            self._render_reactions(nodes, results)

        # ---- view ----
        if pv.OFF_SCREEN:
            self.plotter.view_xy()
            self.plotter.show_axes()
            self.plotter.set_viewup((0, 1, 0))

    # ------------------------------------------------------------------
    # Private render helpers
    # ------------------------------------------------------------------

    def _render_undeformed_model(self, members: list) -> None:
        """Draw members in a faded colour as reference."""
        for member in members:
            line = pv.Line(
                (member.start_node.X, member.start_node.Y, member.start_node.Z),
                (member.end_node.X, member.end_node.Y, member.end_node.Z),
            )
            self.plotter.add_mesh(line, color="lightgray", line_width=1)

    def _render_deformed_members(
        self,
        members: list,
        node_displacements: dict,
        results: "SingleResults",
    ) -> None:
        """Delegate deformed-shape rendering to each :class:`MemberResult`."""
        member_results = getattr(results, "member_results", {}) or {}
        zeros = np.zeros(3, dtype=float)
        labeled_original = False
        labeled_deformed = False

        for member in members:
            d0, r0 = node_displacements.get(member.start_node.id, (zeros, zeros))
            d1, r1 = node_displacements.get(member.end_node.id, (zeros, zeros))

            mr = member_results.get(str(member.id))
            if mr is not None and hasattr(mr, "render_deformed_shape"):
                meshes = mr.render_deformed_shape(
                    member,
                    d0,
                    r0,
                    d1,
                    r1,
                    scale=self.deformed_scale,
                    num_points=self.num_points,
                )
                for mesh, color, lw in meshes:
                    if color == "blue" and not labeled_original:
                        self.plotter.add_mesh(
                            mesh,
                            color=color,
                            line_width=lw,
                            label="Original Shape",
                        )
                        labeled_original = True
                    elif color == "red" and not labeled_deformed:
                        self.plotter.add_mesh(
                            mesh,
                            color=color,
                            line_width=lw,
                            label="Deformed Shape",
                        )
                        labeled_deformed = True
                    else:
                        self.plotter.add_mesh(mesh, color=color, line_width=lw)
            else:
                # Fallback: simple straight-line deformation
                p0 = (
                    np.array(
                        [member.start_node.X, member.start_node.Y, member.start_node.Z],
                        dtype=float,
                    )
                    + d0 * self.deformed_scale
                )
                p1 = (
                    np.array(
                        [member.end_node.X, member.end_node.Y, member.end_node.Z],
                        dtype=float,
                    )
                    + d1 * self.deformed_scale
                )
                line = pv.Line(tuple(p0), tuple(p1))
                label = "Deformed Shape" if not labeled_deformed else None
                self.plotter.add_mesh(
                    line,
                    color="red",
                    line_width=2,
                    label=label,
                )
                labeled_deformed = True

    def _render_nodes(
        self,
        nodes: list,
        node_displacements: dict,
        results: Optional["SingleResults"],
    ) -> None:
        """Render nodes; if deformed mode, delegate to :class:`NodeDisplacement`."""
        disp_nodes: dict = {}
        if results is not None:
            disp_nodes = getattr(results, "displacement_nodes", {}) or {}

        labeled_original = False
        labeled_deformed = False

        for node in nodes:
            pos = np.array([node.X, node.Y, node.Z], dtype=float)

            # Original node
            sphere_orig = pv.Sphere(center=tuple(pos), radius=0.2 * self.annotation_size)
            label_o = "Original Nodes" if not labeled_original else None
            self.plotter.add_mesh(sphere_orig, color="blue", label=label_o)
            labeled_original = True

            # Displaced node
            if self.deformed_shape and str(node.id) in disp_nodes:
                disp = disp_nodes[str(node.id)]
                if disp is not None and hasattr(disp, "render_displaced_node"):
                    meshes = disp.render_displaced_node(
                        pos,
                        scale=self.deformed_scale,
                        annotation_size=self.annotation_size,
                    )
                    for mesh, color in meshes:
                        label_d = "Deformed Nodes" if not labeled_deformed else None
                        self.plotter.add_mesh(mesh, color=color, label=label_d)
                        labeled_deformed = True

    def _render_diagrams(self, members: list, results: "SingleResults") -> None:
        """Delegate diagram rendering to each :class:`MemberResult`."""
        member_results = getattr(results, "member_results", {}) or {}
        for member in members:
            mr = member_results.get(str(member.id))
            if mr is None or not hasattr(mr, "render_diagram"):
                continue
            meshes = mr.render_diagram(
                member,
                self.member_diagrams,
                scale=self.diagram_scale,
                num_points=self.num_points,
            )
            for mesh, color, lw in meshes:
                self.plotter.add_mesh(mesh, color=color, line_width=lw)

    def _render_reactions(self, nodes: list, results: "SingleResults") -> None:
        """Delegate reaction rendering to each :class:`ReactionNodeResult`."""
        reaction_nodes = getattr(results, "reaction_nodes", {}) or {}
        if not reaction_nodes:
            return

        # Compute max magnitude for relative scaling
        max_mag = 0.0
        for reaction in reaction_nodes.values():
            fv = np.array(
                [reaction.nodal_forces.fx, reaction.nodal_forces.fy, reaction.nodal_forces.fz],
                dtype=float,
            )
            mag = float(np.linalg.norm(fv))
            if mag > max_mag:
                max_mag = mag

        if max_mag <= 0.0:
            return

        arrow_scale = self.annotation_size * 5.0
        labeled = False

        for nid_str, reaction in reaction_nodes.items():
            # Find the node position
            node = self.model.get_node_by_pk(int(nid_str))
            if node is not None:
                pos = np.array([node.X, node.Y, node.Z], dtype=float)
            else:
                loc = reaction.location
                pos = np.array([loc.X, loc.Y, loc.Z], dtype=float)

            if hasattr(reaction, "render_reaction"):
                meshes = reaction.render_reaction(
                    pos,
                    max_force_magnitude=max_mag,
                    arrow_scale=arrow_scale,
                )
                for mesh, color in meshes:
                    lbl = "Reaction Forces" if not labeled else None
                    self.plotter.add_mesh(mesh, color=color, label=lbl)
                    labeled = True
            else:
                # Fallback: simple arrows via plotter
                fv = np.array(
                    [reaction.nodal_forces.fx, reaction.nodal_forces.fy, reaction.nodal_forces.fz],
                    dtype=float,
                )
                mag = float(np.linalg.norm(fv))
                if mag <= 0.0:
                    continue
                direction = fv / mag
                lbl = "Reaction Forces" if not labeled else None
                self.plotter.add_arrows(
                    pos,
                    direction * arrow_scale * (mag / max_mag),
                    color="magenta",
                    label=lbl,
                )
                labeled = True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show(
        self,
        jupyter_backend: str = "trame",
        screenshot: Optional[str] = None,
    ) -> None:
        """Update and display the rendered results.

        Args:
            jupyter_backend: Backend to use in Jupyter notebooks.
            screenshot: Path to save a screenshot, if provided.
        """
        self.update()

        self.plotter.add_legend()
        self.plotter.show_grid(color="gray")
        self.plotter.view_isometric()

        if screenshot:
            self.plotter.screenshot(screenshot)

        title = "Results"
        results = self._get_active_results()
        if results is not None and hasattr(results, "name"):
            title = f'Results: "{results.name}"'

        return self.plotter.show(jupyter_backend=jupyter_backend, title=title)

    def screenshot(self, filename: str) -> None:
        """Save a screenshot of the current view.

        Args:
            filename: Path to save the screenshot.
        """
        self.update()
        self.plotter.screenshot(filename)

    def close(self) -> None:
        """Close the plotter."""
        self.plotter.close()
