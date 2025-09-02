from typing import List, Optional
import matplotlib.pyplot as plt

from ..members.shapecommand import ShapeCommand

import numpy as np
import math


class ShapePath:
    _shape_counter = 1

    def __init__(self, name: str, shape_commands: List[ShapeCommand], id: Optional[int] = None):
        """
        Initializes a ShapePath object.
        Parameters:
        name (str): Name of the shape (e.g., "IPE100", "RHS 100x50x4").
        shape_commands (List[ShapeCommand]): List of shape commands defining the section geometry.
        id (int, optional): Unique identifier for the shape path.
        """
        self.id = id or ShapePath._shape_counter
        if id is None:
            ShapePath._shape_counter += 1
        self.name = name
        self.shape_commands = shape_commands

    @classmethod
    def reset_counter(cls):
        cls._shape_counter = 1

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "shape_commands": [cmd.to_dict() for cmd in self.shape_commands],
        }

    @staticmethod
    def arc_cubic(
        center_y: float,
        center_z: float,
        radius: float,
        start_angle_rad: float,
        end_angle_rad: float,
        move_to_start: bool = False,
    ) -> List[ShapeCommand]:
        """
        Returns commands for a circular arc approximated by cubic Bézier segments.
        Parameterization used here (consistent with your yz plotting):
            z(theta) = center_z + radius * sin(theta)
            y(theta) = center_y + radius * cos(theta)
        So theta = 0 lies on +y from the center, and theta increases counterclockwise
        (toward +z then -y, etc.).
        The arc is subdivided into segments with |Δθ| ≤ π/2. Each segment uses the exact
        k-formula: k = 4/3 * tan(Δθ/4).
        If move_to_start = True, the first command will be a moveTo to the start point.
        Otherwise, it assumes your current pen position already equals the start point.
        """
        commands: List[ShapeCommand] = []

        # Normalize angle direction
        total = end_angle_rad - start_angle_rad
        if total == 0.0 or radius <= 0.0:
            return commands

        # Decide direction and step
        direction = 1.0 if total > 0.0 else -1.0
        remaining = abs(total)

        current = start_angle_rad
        # Add a moveTo to the start if requested
        start_z = center_z + radius * math.sin(current)
        start_y = center_y + radius * math.cos(current)
        if move_to_start:
            commands.append(ShapeCommand("moveTo", y=start_y, z=start_z))

        while remaining > 1e-12:
            dtheta = min(remaining, math.pi / 2.0)
            remaining -= dtheta
            dtheta *= direction

            theta0 = current
            theta1 = current + dtheta

            # Endpoints
            z0 = center_z + radius * math.sin(theta0)
            y0 = center_y + radius * math.cos(theta0)
            z3 = center_z + radius * math.sin(theta1)
            y3 = center_y + radius * math.cos(theta1)

            # Tangent directions at endpoints (derivatives)
            # dz/dθ = radius * cos(θ), dy/dθ = -radius * sin(θ)
            dz0_dtheta = radius * math.cos(theta0)
            dy0_dtheta = -radius * math.sin(theta0)
            dz1_dtheta = radius * math.cos(theta1)
            dy1_dtheta = -radius * math.sin(theta1)

            # Bézier control distance factor
            k = (4.0 / 3.0) * math.tan((theta1 - theta0) / 4.0)

            # Control points in (z, y)
            z1 = z0 + k * dz0_dtheta
            y1 = y0 + k * dy0_dtheta
            z2 = z3 - k * dz1_dtheta
            y2 = y3 - k * dy1_dtheta

            commands.append(
                ShapeCommand(
                    "cubicTo",
                    y=y3,
                    z=z3,
                    control_y1=y1,
                    control_z1=z1,
                    control_y2=y2,
                    control_z2=z2,
                )
            )

            current = theta1

        return commands

    @staticmethod
    def quarter_fillet_hv(
        corner_y: float,
        corner_z: float,
        radius: float,
        quadrant: str,
        move_to_start: bool = False,
        convex: bool = False,  # False = inner (concave), True = outer (convex)
    ) -> List["ShapeCommand"]:
        """
        Draw a 90° fillet at the intersection of a horizontal and a vertical edge.

        Coordinates on the yz plane (y horizontal, z vertical). The parameterization
        in arc_cubic is:
            y(θ) = cy + r * cos(θ)
            z(θ) = cz + r * sin(θ)
        with θ increasing counterclockwise.

        Arguments:
            corner_y, corner_z: the sharp intersection point of the two edges (before filleting)
            radius: fillet radius
            quadrant: one of {"top-right","top-left","bottom-right","bottom-left"} naming the corner
            move_to_start: if True, emit a moveTo to the fillet's start point
            convex: set to True for an outer (convex) fillet, False for an inner (concave) fillet

        Notes:
            - Center offset:
                Inner (concave):   cy = corner_y + ( +r if "right"  else -r )
                                    cz = corner_z + ( +r if "bottom" else -r )
                Outer (convex):    cy = corner_y + ( -r if "right"  else +r )
                                    cz = corner_z + ( +r if "bottom" else -r )
            That is: Z-shift follows bottom/top in both cases; the Y-shift flips sign between inner and outer.

            - Start/end angles are chosen so the arc begins exactly at the tangent point
            you typically reach with a prior lineTo in a clockwise perimeter build.
        """
        if radius <= 0.0:
            return []

        q = quadrant.lower()
        if q not in ("top-right", "top-left", "bottom-right", "bottom-left"):
            raise ValueError("quadrant must be one of: top-right, top-left, bottom-right, bottom-left")

        # ----- center (cy, cz)
        if not convex:
            # Inner (concave) fillet
            dy = radius if "right" in q else -radius
            dz = radius if "bottom" in q else -radius
        else:
            # Outer (convex) fillet
            dy = -radius if "right" in q else radius
            dz = radius if "bottom" in q else -radius
        cy = corner_y + dy
        cz = corner_z + dz

        # ----- angle mapping (θ0 -> θ1). These match common path orders used in profiles.
        if not convex:
            # Inner fillets (concave)
            if q == "top-right":
                theta0, theta1 = 0.0, -math.pi / 2.0
            elif q == "top-left":
                theta0, theta1 = math.pi / 2.0, 0.0
            elif q == "bottom-right":
                theta0, theta1 = -math.pi / 2.0, -math.pi
            else:  # "bottom-left"
                theta0, theta1 = math.pi, math.pi / 2.0
        else:
            # Outer fillets (convex)
            if q == "bottom-right":
                theta0, theta1 = 0.0, -math.pi / 2.0
            elif q == "bottom-left":
                theta0, theta1 = math.pi, 1.5 * math.pi
            elif q == "top-left":
                theta0, theta1 = math.pi / 2.0, math.pi
            else:  # "top-right"
                theta0, theta1 = 0.0, math.pi / 2.0

        return ShapePath.arc_cubic(
            center_y=cy,
            center_z=cz,
            radius=radius,
            start_angle_rad=theta0,
            end_angle_rad=theta1,
            move_to_start=move_to_start,
        )

    @staticmethod
    def create_ipe_profile(h: float, b: float, t_f: float, t_w: float, r: float) -> List[ShapeCommand]:
        """
        IPE outline with optional root fillets r at web↔flange corners.
        Coordinates: z is horizontal, y is vertical. Centered on origin.
        """
        commands: List[ShapeCommand] = []

        half_b = b / 2.0
        half_h = h / 2.0

        # Useful inner lines
        y_top_inner = half_h - t_f
        y_bot_inner = -half_h + t_f
        z_web_right = t_w / 2.0
        z_web_left = -t_w / 2.0

        # Limit radius so it fits
        r = r

        # Outer rectangle
        commands.append(ShapeCommand("moveTo", z=-half_b, y=+half_h))
        commands.append(ShapeCommand("lineTo", z=+half_b, y=+half_h))
        commands.append(ShapeCommand("lineTo", z=+half_b, y=y_top_inner))

        if r > 0.0:
            # Top-right fillet (inside corner at intersection of top inner and right web inner)
            # Move along the top inner to start point of the fillet
            commands.append(ShapeCommand("lineTo", y=y_top_inner, z=z_web_right + r))
            # Draw the quarter arc
            commands.extend(
                ShapePath.quarter_fillet_hv(
                    corner_y=y_top_inner,
                    corner_z=z_web_right,
                    radius=r,
                    quadrant="top-right",
                    move_to_start=False,
                    convex=True,
                )
            )
            # Continue down the web after the fillet
            commands.append(ShapeCommand("lineTo", y=y_bot_inner + r, z=z_web_right))
            # Bottom-right fillet
            corner_br_y = y_bot_inner
            corner_br_z = z_web_right
            commands.extend(
                ShapePath.quarter_fillet_hv(
                    corner_y=corner_br_y,
                    corner_z=corner_br_z,
                    radius=r,
                    quadrant="bottom-right",
                    move_to_start=False,
                )
            )
            # Across bottom inner flange
            commands.append(ShapeCommand("lineTo", y=y_bot_inner, z=+half_b))
        else:
            # Sharp inner at right
            commands.append(ShapeCommand("lineTo", z=z_web_right, y=y_top_inner))
            commands.append(ShapeCommand("lineTo", z=z_web_right, y=y_bot_inner))
            commands.append(ShapeCommand("lineTo", z=+half_b, y=y_bot_inner))

        # Outer bottom and left
        commands.append(ShapeCommand("lineTo", z=+half_b, y=-half_h))
        commands.append(ShapeCommand("lineTo", z=-half_b, y=-half_h))
        commands.append(ShapeCommand("lineTo", z=-half_b, y=y_bot_inner))

        if r > 0.0:
            # Bottom-left fillet
            corner_bl_y = y_bot_inner
            corner_bl_z = z_web_left
            commands.append(ShapeCommand("lineTo", y=corner_bl_y, z=corner_bl_z - r))
            commands.extend(
                ShapePath.quarter_fillet_hv(
                    corner_y=corner_bl_y,
                    corner_z=corner_bl_z,
                    radius=r,
                    quadrant="bottom-left",
                    move_to_start=False,
                    convex=True,
                )
            )
            # Up the left web to top-left fillet start
            commands.append(ShapeCommand("lineTo", y=y_top_inner - r, z=z_web_left))
            # Top-left fillet
            corner_tl_y = y_top_inner
            corner_tl_z = z_web_left
            commands.extend(
                ShapePath.quarter_fillet_hv(
                    corner_y=corner_tl_y,
                    corner_z=corner_tl_z,
                    radius=r,
                    quadrant="top-left",
                    move_to_start=False,
                )
            )
            # Finish top inner flange
            commands.append(ShapeCommand("lineTo", y=y_top_inner, z=-half_b))
        else:
            # Sharp inner at left
            commands.append(ShapeCommand("lineTo", z=z_web_left, y=y_bot_inner))
            commands.append(ShapeCommand("lineTo", z=z_web_left, y=y_top_inner))
            commands.append(ShapeCommand("lineTo", z=-half_b, y=y_top_inner))

        commands.append(ShapeCommand("closePath"))
        return commands

    @staticmethod
    def create_u_profile(h: float, b: float, t: float, r: float) -> List[ShapeCommand]:
        """
        Channel (U) outline with optional inner root fillets r at web↔flange corners.
        Coordinates: z is horizontal, y is vertical. Centered on origin.
        Open side is on the right (positive z). Web is on the left.

        Inputs:
            h: overall section height
            b: overall section width (left outer web face to right flange tip)
            t: uniform thickness for web and flanges
            r: inner fillet radius at web↔flange corners (0 for sharp)

        Returns:
            List[ShapeCommand] forming a single closed path of the U-section outline.
        """
        commands: List[ShapeCommand] = []

        half_width = b / 2.0
        half_height = h / 2.0

        # Inner faces (for the channel interior)
        inner_top_y = half_height - t - r
        inner_bottom_y = -half_height + t + r
        inner_web_right_z = -half_width + t  # inside face of the web (web is on the left)

        # Outer faces (bounding rectangle)
        outer_left_z = -half_width
        outer_right_z = +half_width
        outer_top_y = +half_height
        outer_bottom_y = -half_height

        radius = r

        # Start at outer top-left corner and go clockwise
        commands.append(ShapeCommand("moveTo", z=outer_left_z, y=outer_top_y))
        commands.append(ShapeCommand("lineTo", z=outer_right_z, y=outer_top_y))

        # Go down the outer right edge to the start of the top flange return
        commands.append(ShapeCommand("lineTo", z=outer_right_z, y=inner_top_y))

        # Top inner flange: go left towards the web inside face
        if radius > 0.0:
            # Approach the fillet start along the top inner edge
            commands.append(ShapeCommand("lineTo", z=inner_web_right_z + radius, y=inner_top_y))
            # Top-left inner fillet at (inner_top_y, inner_web_right_z)
            commands.extend(
                ShapePath.quarter_fillet_hv(
                    corner_y=inner_top_y,
                    corner_z=inner_web_right_z,
                    radius=radius,
                    quadrant="top-left",
                    convex=False,
                )
            )
            # Down along the inside face of the web
            commands.append(ShapeCommand("lineTo", z=inner_web_right_z, y=inner_bottom_y + radius))
            # Bottom-left inner fillet at (inner_bottom_y, inner_web_right_z)
            commands.extend(
                ShapePath.quarter_fillet_hv(
                    corner_y=inner_bottom_y,
                    corner_z=inner_web_right_z,
                    radius=radius,
                    quadrant="bottom-left",
                    move_to_start=False,
                )
            )
            # Across the bottom inner flange back to the mouth
            commands.append(ShapeCommand("lineTo", z=outer_right_z, y=inner_bottom_y))
        else:
            # Sharp inner corners
            commands.append(ShapeCommand("lineTo", z=inner_web_right_z, y=inner_top_y))
            commands.append(ShapeCommand("lineTo", z=inner_web_right_z, y=inner_bottom_y))
            commands.append(ShapeCommand("lineTo", z=outer_right_z, y=inner_bottom_y))

        # Finish the outer perimeter: down to outer bottom-right, across bottom, up left side
        commands.append(ShapeCommand("lineTo", z=outer_right_z, y=outer_bottom_y))
        commands.append(ShapeCommand("lineTo", z=outer_left_z, y=outer_bottom_y))
        commands.append(ShapeCommand("lineTo", z=outer_left_z, y=outer_top_y))

        commands.append(ShapeCommand("closePath"))
        return commands

    def plot(self, show_nodes: bool = True):
        """
        Plots the shape on the yz plane, with y as the horizontal axis and z as the vertical axis.
        Parameters:
        show_nodes (bool): Whether to display node numbers and positions. Default is True.
        """
        y, z = [], []
        node_coords = []  # To store node coordinates for plotting
        start_y, start_z = None, None  # To track the starting point for closePath
        node_count = 0

        current_y, current_z = None, None  # Current pen position for bezier starts

        for command in self.shape_commands:
            if command.command == "moveTo":
                if z and y:
                    plt.plot(z, y, "b-")
                    z, y = [], []
                z.append(command.z)
                y.append(command.y)
                node_coords.append((command.z, command.y, node_count))
                start_z, start_y = command.z, command.y
                current_z, current_y = command.z, command.y
                node_count += 1

            elif command.command == "lineTo":
                z.append(command.z)
                y.append(command.y)
                node_coords.append((command.z, command.y, node_count))
                current_z, current_y = command.z, command.y
                node_count += 1

            elif command.command == "cubicTo":
                # Sample a cubic Bézier from (current_z,current_y) to (command.z,command.y)
                assert current_z is not None and current_y is not None, "cubicTo without a current point"
                p0 = np.array([current_z, current_y])
                p1 = np.array([command.control_z1, command.control_y1])
                p2 = np.array([command.control_z2, command.control_y2])
                p3 = np.array([command.z, command.y])

                t_vals = np.linspace(0.0, 1.0, 24)
                curve = (
                    (1 - t_vals)[:, None] ** 3 * p0
                    + 3 * (1 - t_vals)[:, None] ** 2 * t_vals[:, None] * p1
                    + 3 * (1 - t_vals)[:, None] * t_vals[:, None] ** 2 * p2
                    + t_vals[:, None] ** 3 * p3
                )

                # Append all *but* the first point (it equals the current point)
                z.extend(curve[1:, 0].tolist())
                y.extend(curve[1:, 1].tolist())

                # Register only the end point as a node (keep it simple)
                node_coords.append((p3[0], p3[1], node_count))
                current_z, current_y = float(p3[0]), float(p3[1])
                node_count += 1

            elif command.command == "closePath":
                if start_z is not None and start_y is not None:
                    z.append(start_z)
                    y.append(start_y)
                plt.plot(z, y, "b-")
                z, y = [], []

        if show_nodes:
            for ny, nz, nnum in node_coords:
                plt.scatter(ny, nz, color="red")
                plt.text(ny, nz, str(nnum), color="red", fontsize=10, ha="right")

        plt.axvline(0, color="black", linestyle="--")
        plt.axhline(0, color="black", linestyle="--")
        plt.axis("equal")
        plt.title(self.name)
        plt.xlabel("Z (Vertical)")
        plt.ylabel("Y (Horizontal)")
        plt.grid(True)
        plt.show()

    def get_shape_geometry(self):
        """
        Converts the shape commands into nodes and edges for plotting or extrusion.

        Returns:
        - coords (list of tuple): A list of (y, z) coordinates defining the vertices of the shape.
        - edges (list of tuple): A list of (start_index, end_index) representing connections between nodes.
        """
        coords = []  # To store all the (y, z) coordinates
        edges = []  # To store edges as (start_index, end_index)
        start_index = None  # To track the starting index for 'closePath'
        node_index = 0  # Index counter for vertices

        for command in self.shape_commands:
            if command.command == "moveTo":
                # Record the starting point for closePath
                start_index = node_index
                coords.append((command.y, command.z))
                node_index += 1

            elif command.command == "lineTo":
                # Add a vertex and connect it to the previous node
                coords.append((command.y, command.z))
                edges.append((node_index - 1, node_index))
                node_index += 1

            elif command.command == "closePath":
                if start_index is not None:
                    # Close the loop by connecting the last node to the start node
                    edges.append((node_index - 1, start_index))

        return coords, edges
