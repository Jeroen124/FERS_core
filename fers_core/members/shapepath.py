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
    def arc_center_angles(
        center_y: float,
        center_z: float,
        radius: float,
        theta0: float,
        theta1: float,
        move_to_start: bool = False,
    ) -> List[ShapeCommand]:
        """
        Add an arc by true geometric parameters (center, radius, start/end angles).
        Angles in radians. Theta increases CCW with:
            z(theta) = center_z + radius * sin(theta)
            y(theta) = center_y + radius * cos(theta)
        If move_to_start is True, a moveTo is emitted to the arc's start point.
        """
        cmds: List[ShapeCommand] = []

        if radius <= 0.0 or theta0 == theta1:
            return cmds

        if move_to_start:
            z0 = center_z + radius * math.sin(theta0)
            y0 = center_y + radius * math.cos(theta0)
            cmds.append(ShapeCommand("moveTo", y=y0, z=z0))

        cmds.append(
            ShapeCommand(
                "arcTo",
                r=radius,
                center_y=center_y,
                center_z=center_z,
                theta0=theta0,
                theta1=theta1,
            )
        )
        return cmds

    @staticmethod
    def create_ipe_profile(h: float, b: float, t_f: float, t_w: float, r: float) -> List[ShapeCommand]:
        """
        IPE outline with optional root fillets r at web↔flange corners.
        Coordinates: z is horizontal, y is vertical. Centered on origin.
        """
        commands: List[ShapeCommand] = []

        half_b = b / 2.0
        half_h = h / 2.0

        y_top_inner = half_h - t_f
        y_bot_inner = -half_h + t_f
        z_web_right = t_w / 2.0
        z_web_left = -t_w / 2.0

        commands.append(ShapeCommand("moveTo", z=-half_b, y=+half_h))
        commands.append(ShapeCommand("lineTo", z=+half_b, y=+half_h))
        commands.append(ShapeCommand("lineTo", z=+half_b, y=y_top_inner))

        if r > 0.0:
            # ---- Top-right fillet (convex quarter)
            commands.append(ShapeCommand("lineTo", y=y_top_inner, z=z_web_right + r))
            cy, cz = y_top_inner - r, z_web_right + r  # center below the corner
            theta0 = 0.0  # start: +y axis
            theta1 = -math.pi / 2.0  # end: +z axis
            commands.extend(ShapePath.arc_center_angles(cy, cz, r, theta0, theta1))

            commands.append(ShapeCommand("lineTo", y=y_bot_inner + r, z=z_web_right))

            # ---- Bottom-right fillet (concave quarter)
            cy, cz = y_bot_inner + r, z_web_right + r  # center above the corner
            theta0 = -math.pi / 2.0  # start: +z axis
            theta1 = -math.pi  # end: -y axis
            commands.extend(ShapePath.arc_center_angles(cy, cz, r, theta0, theta1))

            commands.append(ShapeCommand("lineTo", y=y_bot_inner, z=+half_b))
        else:
            commands.append(ShapeCommand("lineTo", z=z_web_right, y=y_top_inner))
            commands.append(ShapeCommand("lineTo", z=z_web_right, y=y_bot_inner))
            commands.append(ShapeCommand("lineTo", z=+half_b, y=y_bot_inner))

        commands.append(ShapeCommand("lineTo", z=+half_b, y=-half_h))
        commands.append(ShapeCommand("lineTo", z=-half_b, y=-half_h))
        commands.append(ShapeCommand("lineTo", z=-half_b, y=y_bot_inner))

        if r > 0.0:
            # ---- Bottom-left fillet (convex)
            commands.append(ShapeCommand("lineTo", y=y_bot_inner, z=z_web_left - r))
            cy, cz = y_bot_inner + r, z_web_left - r  # center above the corner
            theta0 = math.pi  # start: -y axis
            theta1 = math.pi / 2  # end: -z axis
            commands.extend(ShapePath.arc_center_angles(cy, cz, r, theta0, theta1))

            commands.append(ShapeCommand("lineTo", y=y_top_inner - r, z=z_web_left))

            # ---- Top-left fillet (concave)
            cy, cz = y_top_inner - r, z_web_left - r  # center below the corner
            theta0 = math.pi / 2.0  # start: -z axis
            theta1 = 0  # end: +y axis
            commands.extend(ShapePath.arc_center_angles(cy, cz, r, theta0, theta1))

            commands.append(ShapeCommand("lineTo", y=y_top_inner, z=-half_b))
        else:
            commands.append(ShapeCommand("lineTo", z=z_web_left, y=y_bot_inner))
            commands.append(ShapeCommand("lineTo", z=z_web_left, y=y_top_inner))
            commands.append(ShapeCommand("lineTo", z=-half_b, y=y_top_inner))

        commands.append(ShapeCommand("closePath"))
        return commands

    @staticmethod
    def create_u_profile(h: float, b: float, t_f: float, t_w: float, r: float) -> List[ShapeCommand]:
        """
        Channel (U) outline with optional inner root fillets r at web↔flange corners.
        Coordinates: z is horizontal, y is vertical. Centered on origin.
        Open side is on the right (positive z). Web is on the left.
        """
        commands: List[ShapeCommand] = []

        half_width = b / 2.0
        half_height = h / 2.0

        inner_top_y = half_height - t_f
        inner_bottom_y = -half_height + t_f
        inner_web_right_z = -half_width + t_w

        outer_left_z = -half_width
        outer_right_z = +half_width
        outer_top_y = +half_height
        outer_bottom_y = -half_height

        commands.append(ShapeCommand("moveTo", z=outer_left_z, y=outer_top_y))
        commands.append(ShapeCommand("lineTo", z=outer_right_z, y=outer_top_y))
        commands.append(ShapeCommand("lineTo", z=outer_right_z, y=inner_top_y))

        if r > 0.0:
            commands.append(ShapeCommand("lineTo", z=inner_web_right_z + r, y=inner_top_y))

            # ---- Top-left inner fillet
            cy, cz = inner_top_y - r, inner_web_right_z + r
            theta0 = 0.0
            theta1 = -math.pi / 2.0
            commands.extend(ShapePath.arc_center_angles(cy, cz, r, theta0, theta1))

            commands.append(ShapeCommand("lineTo", z=inner_web_right_z, y=inner_bottom_y + r))

            # ---- Bottom-left inner fillet
            cy, cz = inner_bottom_y + r, inner_web_right_z + r
            theta0 = -math.pi / 2.0
            theta1 = -math.pi
            commands.extend(ShapePath.arc_center_angles(cy, cz, r, theta0, theta1))

            commands.append(ShapeCommand("lineTo", z=outer_right_z, y=inner_bottom_y))
        else:
            commands.append(ShapeCommand("lineTo", z=inner_web_right_z, y=inner_top_y))
            commands.append(ShapeCommand("lineTo", z=inner_web_right_z, y=inner_bottom_y))
            commands.append(ShapeCommand("lineTo", z=outer_right_z, y=inner_bottom_y))

        commands.append(ShapeCommand("lineTo", z=outer_right_z, y=outer_bottom_y))
        commands.append(ShapeCommand("lineTo", z=outer_left_z, y=outer_bottom_y))
        commands.append(ShapeCommand("lineTo", z=outer_left_z, y=outer_top_y))

        commands.append(ShapeCommand("closePath"))
        return commands

    def plot(self, show_nodes: bool = True):
        """
        Plots the shape on the yz plane, with y as the horizontal axis and z as the vertical axis.
        """
        y, z = [], []
        node_coords = []
        start_y, start_z = None, None
        node_count = 0

        def flush_polyline():
            if z and y:
                plt.plot(z, y, "b-")

        for command in self.shape_commands:
            if command.command == "moveTo":
                if z and y:
                    flush_polyline()
                    z, y = [], []
                z.append(command.z)
                y.append(command.y)
                node_coords.append((command.z, command.y, node_count))
                start_z, start_y = command.z, command.y
                node_count += 1

            elif command.command == "lineTo":
                z.append(command.z)
                y.append(command.y)
                node_coords.append((command.z, command.y, node_count))
                node_count += 1

            elif command.command == "arcTo":
                assert command.center_y is not None and command.center_z is not None
                assert command.r is not None and command.theta0 is not None and command.theta1 is not None

                cy = float(command.center_y)
                cz = float(command.center_z)
                r = float(command.r)
                t0 = float(command.theta0)
                t1 = float(command.theta1)

                delta = t1 - t0
                if abs(delta) < 1e-12 or r <= 0.0:
                    continue

                # Choose segment count: ~10 degrees per segment
                max_dtheta = math.radians(10.0)
                n_seg = max(1, int(math.ceil(abs(delta) / max_dtheta)))

                t_vals = np.linspace(t0, t1, n_seg + 1)
                z_arc = cz + r * np.sin(t_vals)
                y_arc = cy + r * np.cos(t_vals)

                # If arc starts away from current pen, we assume previous command set the start correctly.
                # Append all but the first (to avoid duplicating current point)
                z.extend(z_arc[1:].tolist())
                y.extend(y_arc[1:].tolist())

                # Register the end point as a node
                node_coords.append((z_arc[-1], y_arc[-1], node_count))
                node_count += 1

            elif command.command == "closePath":
                if start_z is not None and start_y is not None:
                    z.append(start_z)
                    y.append(start_y)
                flush_polyline()
                z, y = [], []

        if show_nodes:
            for nz, ny, nnum in node_coords:
                plt.scatter(nz, ny, color="red")
                plt.text(nz, ny, str(nnum), color="red", fontsize=10, ha="right")

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
            coords: List[(y, z)]
            edges:  List[(start_index, end_index)]
        """
        coords = []
        edges = []
        start_index = None
        node_index = 0

        def add_vertex(yv: float, zv: float):
            nonlocal node_index
            coords.append((yv, zv))
            node_index += 1
            return node_index - 1

        for command in self.shape_commands:
            if command.command == "moveTo":
                start_index = add_vertex(command.y, command.z)

            elif command.command == "lineTo":
                prev = node_index - 1
                curr = add_vertex(command.y, command.z)
                edges.append((prev, curr))

            elif command.command == "arcTo":
                cy = float(command.center_y)
                cz = float(command.center_z)
                r = float(command.r)
                t0 = float(command.theta0)
                t1 = float(command.theta1)
                delta = t1 - t0
                if abs(delta) < 1e-12 or r <= 0.0:
                    continue

                max_dtheta = math.radians(10.0)
                n_seg = max(1, int(math.ceil(abs(delta) / max_dtheta)))
                t_vals = np.linspace(t0, t1, n_seg + 1)

                # First sample is expected to coincide with current point,
                # but for robustness, we will still add it only if this arc starts a new sequence
                # We always add subsequent samples as new vertices.
                prev_index = node_index - 1
                for k in range(1, len(t_vals)):  # skip k=0 (start)
                    yk = cy + r * math.cos(t_vals[k])
                    zk = cz + r * math.sin(t_vals[k])
                    curr_index = add_vertex(yk, zk)
                    edges.append((prev_index, curr_index))
                    prev_index = curr_index

            elif command.command == "closePath":
                if start_index is not None and node_index > 0:
                    edges.append((node_index - 1, start_index))

        return coords, edges
