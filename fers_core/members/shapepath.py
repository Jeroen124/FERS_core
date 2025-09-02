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
    ) -> List[ShapeCommand]:
        """
        90-degree fillet at the inside corner between a horizontal and a vertical segment.

        The 'corner' is the sharp (un-filleted) intersection of the horizontal and vertical.
        The arc center is shifted one radius "into the material":
            top    → cy = corner_y - r
            bottom → cy = corner_y + r
            right  → cz = corner_z + r
            left   → cz = corner_z - r

        Parameterization (consistent with arc_cubic):
            y(θ) = cy + r * cos(θ)
            z(θ) = cz + r * sin(θ)

        IMPORTANT: θ increases counterclockwise. Depending on the quadrant and your traversal
        direction, the inside fillet may be clockwise (decreasing θ). The start angle θ0 is
        chosen to match the tangent point you lineTo just before calling this function; the
        end angle θ1 is θ0 ± π/2 so we draw exactly one quarter circle.

        Correct angle mapping for inside fillets when you approach each corner in a standard
        I-section loop (like your create_ipe_profile):

            top-right:    θ0 = 0,         θ1 = -π/2
            top-left:     θ0 =  π/2,      θ1 = 0
            bottom-right: θ0 = -π/2,      θ1 = -π
            bottom-left:  θ0 =  π,        θ1 =  π/2
        """
        quadrant = quadrant.lower()
        if radius <= 0.0:
            return []

        # Compute arc center from corner and quadrant (toward the material)
        dy = -radius if "top" in quadrant else radius
        dz = radius if "right" in quadrant else -radius
        cy = corner_y + dy
        cz = corner_z + dz

        # Pick start/end angles so the arc begins at the tangent point you just reached
        # with lineTo, and turns exactly 90° along the inside.
        if quadrant == "top-right":
            theta0 = 0.0
            theta1 = -math.pi / 2.0
        elif quadrant == "top-left":
            theta0 = math.pi / 2.0
            theta1 = 0.0
        elif quadrant == "bottom-right":
            theta0 = -math.pi / 2.0
            theta1 = -math.pi
        elif quadrant == "bottom-left":
            theta0 = math.pi
            theta1 = math.pi / 2.0
        else:
            raise ValueError("quadrant must be one of: top-right, top-left, bottom-right, bottom-left")

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
