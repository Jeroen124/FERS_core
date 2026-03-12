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

    @classmethod
    def from_dict(cls, data: dict) -> "ShapePath":
        """
        Inverse of to_dict.

        Expects:
          {
            "id": int,
            "name": str,
            "shape_commands": [
              {
                "command": "moveTo" | "lineTo" | "arcTo" | "closePath",
                ... other ShapeCommand fields ...
              },
              ...
            ]
          }
        """
        commands_data = data.get("shape_commands", []) or []
        commands: List[ShapeCommand] = []

        for command_data in commands_data:
            command_data = ShapeCommand.from_dict(command_data)

        return cls(
            name=data["name"],
            shape_commands=commands,
            id=data.get("id"),
        )

    @staticmethod
    def from_dxf(filepath: str, name: Optional[str] = None, layer: Optional[str] = None) -> "ShapePath":
        """
        Import a cross-section outline from a DXF file and return a ShapePath.

        Supported DXF entities: LINE, LWPOLYLINE, ARC, CIRCLE.
        DXF coordinates are mapped as: DXF-X → ShapePath-z, DXF-Y → ShapePath-y.

        Parameters:
            filepath (str): Path to the .dxf file.
            name (str, optional): Name for the ShapePath. Defaults to the filename stem.
            layer (str, optional): If given, only entities on this layer are imported.
        """
        try:
            import ezdxf
        except ImportError:
            raise ImportError("ezdxf is required for DXF import. Install it with: pip install ezdxf")

        import os

        doc = ezdxf.readfile(filepath)
        msp = doc.modelspace()

        if name is None:
            name = os.path.splitext(os.path.basename(filepath))[0]

        commands: List[ShapeCommand] = []

        for entity in msp:
            if layer is not None and entity.dxf.layer != layer:
                continue

            dxftype = entity.dxftype()

            if dxftype == "LINE":
                sx, sy = entity.dxf.start.x, entity.dxf.start.y
                ex, ey = entity.dxf.end.x, entity.dxf.end.y
                commands.append(ShapeCommand("moveTo", z=sx, y=sy))
                commands.append(ShapeCommand("lineTo", z=ex, y=ey))

            elif dxftype == "LWPOLYLINE":
                points = list(entity.get_points(format="xyseb"))  # x, y, start_width, end_width, bulge
                if not points:
                    continue
                closed = entity.closed

                for i, pt in enumerate(points):
                    px, py, _sw, _ew, bulge = pt
                    if i == 0:
                        commands.append(ShapeCommand("moveTo", z=px, y=py))
                    else:
                        prev_pt = points[i - 1]
                        prev_bulge = prev_pt[4]
                        if abs(prev_bulge) > 1e-9:
                            # Convert bulge to arc
                            x0, y0 = prev_pt[0], prev_pt[1]
                            x1, y1 = px, py
                            b = prev_bulge
                            # Chord midpoint and distance
                            d = math.hypot(x1 - x0, y1 - y0)
                            r_arc = d * (1 + b * b) / (4 * abs(b))
                            # Center of arc
                            alpha = math.atan2(y1 - y0, x1 - x0)
                            theta_half = 2 * math.atan(b)
                            cx = (x0 + x1) / 2 - r_arc * math.sin(theta_half) * math.cos(
                                alpha + math.pi / 2 * (1 if b > 0 else -1)
                            )
                            cy = (y0 + y1) / 2 - r_arc * math.sin(theta_half) * math.sin(
                                alpha + math.pi / 2 * (1 if b > 0 else -1)
                            )
                            t0_arc = math.atan2(y0 - cy, x0 - cx)
                            t1_arc = math.atan2(y1 - cy, x1 - cx)
                            # Adjust angles for CCW/CW convention used by arc_center_angles
                            # ShapePath arcTo: z = cz + r*sin(t), y = cy + r*cos(t)
                            # DXF arc in XY: x = cx + r*cos(a), y = cy + r*sin(a)
                            # Convert: shapepath theta = pi/2 - dxf_angle
                            sp_t0 = math.pi / 2 - t0_arc
                            sp_t1 = math.pi / 2 - t1_arc
                            if b < 0:
                                # CW arc: ensure t1 < t0
                                while sp_t1 > sp_t0:
                                    sp_t1 -= 2 * math.pi
                            else:
                                # CCW arc: ensure t1 > t0
                                while sp_t1 < sp_t0:
                                    sp_t1 += 2 * math.pi
                            commands.extend(ShapePath.arc_center_angles(cy, cx, r_arc, sp_t0, sp_t1))
                        else:
                            commands.append(ShapeCommand("lineTo", z=px, y=py))

                if closed:
                    commands.append(ShapeCommand("closePath"))

            elif dxftype == "ARC":
                cx, cy = entity.dxf.center.x, entity.dxf.center.y
                r_arc = entity.dxf.radius
                # DXF angles are in degrees, CCW from +X axis
                a0 = math.radians(entity.dxf.start_angle)
                a1 = math.radians(entity.dxf.end_angle)
                if a1 <= a0:
                    a1 += 2 * math.pi
                # Convert to ShapePath theta convention
                sp_t0 = math.pi / 2 - a0
                sp_t1 = math.pi / 2 - a1
                # Emit moveTo start of arc
                start_z = cx + r_arc * math.cos(a0)
                start_y = cy + r_arc * math.sin(a0)
                commands.append(ShapeCommand("moveTo", z=start_z, y=start_y))
                commands.extend(ShapePath.arc_center_angles(cy, cx, r_arc, sp_t0, sp_t1))

            elif dxftype == "CIRCLE":
                cx, cy = entity.dxf.center.x, entity.dxf.center.y
                r_arc = entity.dxf.radius
                start_z = cx + r_arc
                start_y = cy
                commands.append(ShapeCommand("moveTo", z=start_z, y=start_y))
                # Full CCW circle: theta goes from pi/2 to pi/2 - 2pi
                commands.extend(
                    ShapePath.arc_center_angles(cy, cx, r_arc, math.pi / 2, math.pi / 2 - 2 * math.pi)
                )

        return ShapePath(name=name, shape_commands=commands)

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

    @staticmethod
    def create_chs_profile(d: float, t: float, n: int = 64) -> List[ShapeCommand]:
        """
        Circular Hollow Section (CHS) as two concentric circular paths:
        - Outer contour traced counter-clockwise
        - Inner contour (the hole) traced clockwise

        Angles follow arc_center_angles convention:
            z(theta) = center_z + radius * sin(theta)
            y(theta) = center_y + radius * cos(theta)

        Parameters:
            d (float): Outside diameter
            t (float): Wall thickness
            n (int):  Angular segmentation target for plotting (the arcTo command
                      itself is analytic; n only affects plot sampling in your plot() method)
        """
        assert d > 0.0 and t > 0.0 and t < d / 2.0, "CHS requires 0 < t < d/2 and d > 0"

        commands: List[ShapeCommand] = []

        center_y = 0.0
        center_z = 0.0
        radius_outer = d / 2.0
        radius_inner = radius_outer - t

        # ---- Outer circle (CCW): start at theta=0 (top), go to 2π
        start_y_outer = center_y + radius_outer * math.cos(0.0)
        start_z_outer = center_z + radius_outer * math.sin(0.0)
        commands.append(ShapeCommand("moveTo", y=start_y_outer, z=start_z_outer))
        commands.extend(
            ShapePath.arc_center_angles(
                center_y=center_y,
                center_z=center_z,
                radius=radius_outer,
                theta0=0.0,
                theta1=2.0 * math.pi,
            )
        )

        # ---- Inner circle (hole) (CW): start at theta=0 (top), go to -2π
        start_y_inner = center_y + radius_inner * math.cos(0.0)
        start_z_inner = center_z + radius_inner * math.sin(0.0)
        commands.append(ShapeCommand("moveTo", y=start_y_inner, z=start_z_inner))
        commands.extend(
            ShapePath.arc_center_angles(
                center_y=center_y,
                center_z=center_z,
                radius=radius_inner,
                theta0=0.0,
                theta1=-2.0 * math.pi,
            )
        )

        return commands

    @staticmethod
    def create_he_profile(h: float, b: float, t_f: float, t_w: float, r: float) -> List[ShapeCommand]:
        """
        HE (wide-flange H) outline with optional root fillets r at web↔flange corners.
        Geometry/topology is identical to the IPE routine, but HE dimensions differ.
        This delegates to create_ipe_profile to keep one robust implementation.
        """
        return ShapePath.create_ipe_profile(h=h, b=b, t_f=t_f, t_w=t_w, r=r)

    @staticmethod
    def create_rhs_profile(h: float, b: float, t: float, r_out: float = 0.0) -> List[ShapeCommand]:
        """
        Rectangular Hollow Section (RHS / SHS) outline.
        Outer rectangle with optional corner radii, inner rectangle as hole.
        Coordinates: z horizontal, y vertical. Centered on origin.

        Parameters:
            h: Total height (y-direction).
            b: Total width (z-direction).
            t: Wall thickness.
            r_out: Outer corner radius (0 for sharp corners).
        """
        commands: List[ShapeCommand] = []
        half_h = h / 2.0
        half_b = b / 2.0
        r_in = max(0.0, r_out - t)

        # ---- Outer contour (CCW) ----
        if r_out > 0.0:
            # Start at top-left, just right of the top-left radius
            commands.append(ShapeCommand("moveTo", z=-half_b + r_out, y=+half_h))
            # Top edge → top-right corner
            commands.append(ShapeCommand("lineTo", z=+half_b - r_out, y=+half_h))
            commands.extend(
                ShapePath.arc_center_angles(half_h - r_out, half_b - r_out, r_out, 0.0, -math.pi / 2.0)
            )
            # Right edge → bottom-right corner
            commands.append(ShapeCommand("lineTo", z=+half_b, y=-half_h + r_out))
            commands.extend(
                ShapePath.arc_center_angles(-half_h + r_out, half_b - r_out, r_out, -math.pi / 2.0, -math.pi)
            )
            # Bottom edge → bottom-left corner
            commands.append(ShapeCommand("lineTo", z=-half_b + r_out, y=-half_h))
            commands.extend(
                ShapePath.arc_center_angles(
                    -half_h + r_out, -half_b + r_out, r_out, -math.pi, -3.0 * math.pi / 2.0
                )
            )
            # Left edge → top-left corner
            commands.append(ShapeCommand("lineTo", z=-half_b, y=+half_h - r_out))
            commands.extend(
                ShapePath.arc_center_angles(
                    half_h - r_out, -half_b + r_out, r_out, -3.0 * math.pi / 2.0, -2.0 * math.pi
                )
            )
        else:
            commands.append(ShapeCommand("moveTo", z=-half_b, y=+half_h))
            commands.append(ShapeCommand("lineTo", z=+half_b, y=+half_h))
            commands.append(ShapeCommand("lineTo", z=+half_b, y=-half_h))
            commands.append(ShapeCommand("lineTo", z=-half_b, y=-half_h))
        commands.append(ShapeCommand("closePath"))

        # ---- Inner contour (hole, CW) ----
        ih = half_h - t
        ib = half_b - t
        if r_in > 0.0:
            commands.append(ShapeCommand("moveTo", z=-ib + r_in, y=+ih))
            commands.append(ShapeCommand("lineTo", z=+ib - r_in, y=+ih))
            commands.extend(ShapePath.arc_center_angles(ih - r_in, ib - r_in, r_in, 0.0, -math.pi / 2.0))
            commands.append(ShapeCommand("lineTo", z=+ib, y=-ih + r_in))
            commands.extend(
                ShapePath.arc_center_angles(-ih + r_in, ib - r_in, r_in, -math.pi / 2.0, -math.pi)
            )
            commands.append(ShapeCommand("lineTo", z=-ib + r_in, y=-ih))
            commands.extend(
                ShapePath.arc_center_angles(-ih + r_in, -ib + r_in, r_in, -math.pi, -3.0 * math.pi / 2.0)
            )
            commands.append(ShapeCommand("lineTo", z=-ib, y=+ih - r_in))
            commands.extend(
                ShapePath.arc_center_angles(ih - r_in, -ib + r_in, r_in, -3.0 * math.pi / 2.0, -2.0 * math.pi)
            )
        else:
            commands.append(ShapeCommand("moveTo", z=-ib, y=+ih))
            commands.append(ShapeCommand("lineTo", z=+ib, y=+ih))
            commands.append(ShapeCommand("lineTo", z=+ib, y=-ih))
            commands.append(ShapeCommand("lineTo", z=-ib, y=-ih))
        commands.append(ShapeCommand("closePath"))

        return commands

    @staticmethod
    def create_angle_profile(
        h: float,
        b: float,
        t: float,
        r_root: float = 0.0,
        r_toe: float = 0.0,
    ) -> List[ShapeCommand]:
        """
        Equal or unequal angle (L) section outline.
        Centered on the geometric centroid of the gross section.
        Vertical leg along y, horizontal leg along z.

        Parameters:
            h: Height of the vertical leg.
            b: Width of the horizontal leg.
            t: Uniform thickness.
            r_root: Root radius at the inner corner.
            r_toe: Toe radius at the tips (ignored for simplicity in path).
        """
        commands: List[ShapeCommand] = []

        # Centroid offsets for an angle with legs along +y and +z from origin
        area = (h + b - t) * t
        z_c = (b * t * (b / 2.0) + (h - t) * t * (t / 2.0)) / area
        y_c = (t * h * (h / 2.0) + (b - t) * t * (t / 2.0)) / area

        # Shift so centroid is at origin
        def p(z: float, y: float):
            return z - z_c, y - y_c

        # Trace the L-shape outline CCW from bottom-left
        z0, y0 = p(0.0, 0.0)
        commands.append(ShapeCommand("moveTo", z=z0, y=y0))

        z1, y1 = p(b, 0.0)
        commands.append(ShapeCommand("lineTo", z=z1, y=y1))

        z2, y2 = p(b, t)
        commands.append(ShapeCommand("lineTo", z=z2, y=y2))

        if r_root > 0.0:
            z3, y3 = p(t + r_root, t)
            commands.append(ShapeCommand("lineTo", z=z3, y=y3))
            # Inner corner fillet — use the shifted coordinates directly
            fillet_cy = t + r_root - y_c
            fillet_cz = t + r_root - z_c
            commands.extend(
                ShapePath.arc_center_angles(fillet_cy, fillet_cz, r_root, -math.pi, -math.pi / 2.0)
            )
            z4, y4 = p(t, t + r_root)
            commands.append(ShapeCommand("lineTo", z=z4, y=y4))
        else:
            z3, y3 = p(t, t)
            commands.append(ShapeCommand("lineTo", z=z3, y=y3))

        z5, y5 = p(t, h)
        commands.append(ShapeCommand("lineTo", z=z5, y=y5))

        z6, y6 = p(0.0, h)
        commands.append(ShapeCommand("lineTo", z=z6, y=y6))

        commands.append(ShapeCommand("closePath"))
        return commands

    @staticmethod
    def create_welded_i_profile(
        h: float,
        b: float,
        t_f: float,
        t_w: float,
    ) -> List[ShapeCommand]:
        """
        Welded I-section (no root radius). Identical topology to IPE but with r=0.
        Centered on origin.
        """
        return ShapePath.create_ipe_profile(h=h, b=b, t_f=t_f, t_w=t_w, r=0.0)

    @staticmethod
    def create_cfs_c_profile(
        h: float,
        b: float,
        lip: float,
        t: float,
        r_out: float = 0.0,
    ) -> List[ShapeCommand]:
        """
        Cold-formed steel C-section (lipped channel) outline.
        Thin-walled representation using the mid-line.
        Centered on origin. Open on the right.

        Parameters:
            h: Total depth.
            b: Flange width.
            lip: Lip length (can be 0).
            t: Wall thickness.
            r_out: Outer bend radius.
        """
        commands: List[ShapeCommand] = []
        half_h = h / 2.0

        # Outer contour
        if lip > 0:
            commands.append(ShapeCommand("moveTo", z=b, y=half_h - lip))
            commands.append(ShapeCommand("lineTo", z=b, y=half_h))
        else:
            commands.append(ShapeCommand("moveTo", z=b, y=half_h))

        commands.append(ShapeCommand("lineTo", z=0.0, y=half_h))
        commands.append(ShapeCommand("lineTo", z=0.0, y=-half_h))
        commands.append(ShapeCommand("lineTo", z=b, y=-half_h))

        if lip > 0:
            commands.append(ShapeCommand("lineTo", z=b, y=-half_h + lip))
            commands.append(ShapeCommand("lineTo", z=b - t, y=-half_h + lip))

        commands.append(ShapeCommand("lineTo", z=b - t, y=-half_h + t))
        commands.append(ShapeCommand("lineTo", z=t, y=-half_h + t))
        commands.append(ShapeCommand("lineTo", z=t, y=half_h - t))
        commands.append(ShapeCommand("lineTo", z=b - t, y=half_h - t))

        if lip > 0:
            commands.append(ShapeCommand("lineTo", z=b - t, y=half_h - lip))

        commands.append(ShapeCommand("closePath"))
        return commands

    @staticmethod
    def create_cfs_z_profile(
        h: float,
        b_top: float,
        b_bot: float,
        lip: float,
        t: float,
        r_out: float = 0.0,
    ) -> List[ShapeCommand]:
        """
        Cold-formed steel Z-section (lipped zed) outline.
        Flanges extend in opposite directions. Centered on origin.

        Parameters:
            h: Total depth.
            b_top: Top flange width (extends in +z).
            b_bot: Bottom flange width (extends in -z).
            lip: Lip length (can be 0).
            t: Wall thickness.
            r_out: Outer bend radius.
        """
        commands: List[ShapeCommand] = []
        half_h = h / 2.0
        half_tw = t / 2.0

        # Outer contour of Z shape
        # Start at top-right lip
        if lip > 0:
            commands.append(ShapeCommand("moveTo", z=b_top, y=half_h - lip))
            commands.append(ShapeCommand("lineTo", z=b_top, y=half_h))
        else:
            commands.append(ShapeCommand("moveTo", z=b_top, y=half_h))

        # Top flange left → web top
        commands.append(ShapeCommand("lineTo", z=-half_tw, y=half_h))
        commands.append(ShapeCommand("lineTo", z=-half_tw, y=-half_h + t))

        # Bottom flange extends in -z direction
        commands.append(ShapeCommand("lineTo", z=-b_bot, y=-half_h + t))

        if lip > 0:
            commands.append(ShapeCommand("lineTo", z=-b_bot, y=-half_h + lip))
            commands.append(ShapeCommand("lineTo", z=-b_bot + t, y=-half_h + lip))

        commands.append(ShapeCommand("lineTo", z=-b_bot + t, y=-half_h + t))
        commands.append(ShapeCommand("lineTo", z=half_tw, y=-half_h + t))

        # Web inner right → bottom flange inner
        commands.append(ShapeCommand("lineTo", z=half_tw, y=half_h - t))

        # Top flange inner
        commands.append(ShapeCommand("lineTo", z=b_top - t, y=half_h - t))

        if lip > 0:
            commands.append(ShapeCommand("lineTo", z=b_top - t, y=half_h - lip))

        commands.append(ShapeCommand("closePath"))
        return commands

    @staticmethod
    def stroke_path(
        commands: List[ShapeCommand],
        thickness: float,
        offset: str = "center",
    ) -> List[ShapeCommand]:
        """
        Extrude an open path (centerline) into a closed filled cross-section profile.

        The input path may contain ``moveTo``, ``lineTo``, and ``arcTo`` commands.
        Straight segments are offset by shifting perpendicular to the travel direction.
        Arc segments are offset radially: the circle's radius grows or shrinks by the
        offset distance while the center and sweep angles remain identical.

        Parameters
        ----------
        commands : list of ShapeCommand
            Open path commands defining the centerline or one edge.
        thickness : float
            Extrusion thickness (must be positive).
        offset : {"center", "left", "right"}
            Where the original path sits relative to the extruded shape.

            - ``"center"`` – the input path is the centerline; the shape extends
              ``thickness/2`` to each side.
            - ``"left"``   – the input path is the **right** edge; the shape extends
              ``thickness`` to the left.
            - ``"right"``  – the input path is the **left** edge; the shape extends
              ``thickness`` to the right.

        Returns
        -------
        list of ShapeCommand
            Closed profile (ends with ``closePath``).

        Notes
        -----
        Arc convention (same as :meth:`arc_center_angles`)::

            z(θ) = center_z + r·sin(θ)
            y(θ) = center_y + r·cos(θ)

        For an arc swept in the *increasing-θ* direction (clockwise in the yz-plane
        when z points right and y points up) the left-hand side is the outer arc
        (larger radius). For a *decreasing-θ* arc the relationship is reversed.

        Join style between consecutive offset segments is **bevel** (a straight lineTo
        bridges any gap between the end of one offset segment and the start of the next).
        """
        # ---- parse input into simple geometric segments -----------------------
        # Each segment is a tuple:
        #   ("line", y0, z0, y1, z1)
        #   ("arc",  center_y, center_z, r, theta0, theta1)
        segments = []
        cur_y: Optional[float] = None
        cur_z: Optional[float] = None

        for cmd in commands:
            if cmd.command == "moveTo":
                cur_y, cur_z = cmd.y, cmd.z
            elif cmd.command == "lineTo":
                if cur_y is None:
                    raise ValueError("stroke_path: 'lineTo' before 'moveTo'")
                segments.append(("line", cur_y, cur_z, cmd.y, cmd.z))
                cur_y, cur_z = cmd.y, cmd.z
            elif cmd.command == "arcTo":
                if cur_y is None:
                    raise ValueError("stroke_path: 'arcTo' before 'moveTo'")
                end_z = cmd.center_z + cmd.r * math.sin(cmd.theta1)
                end_y = cmd.center_y + cmd.r * math.cos(cmd.theta1)
                segments.append(("arc", cmd.center_y, cmd.center_z, cmd.r, cmd.theta0, cmd.theta1))
                cur_y, cur_z = end_y, end_z
            elif cmd.command == "closePath":
                break  # open-path input only; stop here

        if not segments:
            return []

        # ---- determine signed offset for each side ----------------------------
        # Positive d → offset to the *left* of the travel direction.
        if offset == "center":
            d_left = thickness / 2.0
            d_right = -thickness / 2.0
        elif offset == "left":
            d_left = thickness
            d_right = 0.0
        elif offset == "right":
            d_left = 0.0
            d_right = -thickness
        else:
            raise ValueError(f"stroke_path: unknown offset '{offset}'. Use 'center', 'left', or 'right'.")

        # ---- helpers ----------------------------------------------------------
        def _offset_seg(seg, d):
            """Return a copy of *seg* shifted *d* to the left of travel direction."""
            if seg[0] == "line":
                _, y0, z0, y1, z1 = seg
                dy = y1 - y0
                dz = z1 - z0
                length = math.hypot(dz, dy)
                if length < 1e-12:
                    return seg
                # Left normal in (z, y): (-dy/len, dz/len)
                nz = -dy / length
                ny = dz / length
                return ("line", y0 + d * ny, z0 + d * nz, y1 + d * ny, z1 + d * nz)
            else:  # arc
                _, cy, cz, r, t0, t1 = seg
                # For increasing θ (CW sweep): left = outward → r + d
                # For decreasing θ (CCW sweep): left = inward  → r - d
                r_new = (r + d) if t1 >= t0 else (r - d)
                if r_new <= 0.0:
                    raise ValueError(
                        f"stroke_path: offset {d} collapses arc radius {r} to {r_new}. "
                        "Reduce thickness or choose a different offset side."
                    )
                return ("arc", cy, cz, r_new, t0, t1)

        def _seg_start(seg):
            """Start point (y, z) of a segment."""
            if seg[0] == "line":
                return seg[1], seg[2]
            _, cy, cz, r, t0, _ = seg
            return cy + r * math.cos(t0), cz + r * math.sin(t0)

        def _seg_end(seg):
            """End point (y, z) of a segment."""
            if seg[0] == "line":
                return seg[3], seg[4]
            _, cy, cz, r, _, t1 = seg
            return cy + r * math.cos(t1), cz + r * math.sin(t1)

        def _seg_to_cmds(seg):
            """Convert a segment to ShapeCommand(s), *without* the initial moveTo."""
            if seg[0] == "line":
                return [ShapeCommand("lineTo", y=seg[3], z=seg[4])]
            _, cy, cz, r, t0, t1 = seg
            return [ShapeCommand("arcTo", r=r, center_y=cy, center_z=cz, theta0=t0, theta1=t1)]

        def _reverse_seg(seg):
            """Reverse a segment's travel direction."""
            if seg[0] == "line":
                _, y0, z0, y1, z1 = seg
                return ("line", y1, z1, y0, z0)
            _, cy, cz, r, t0, t1 = seg
            return ("arc", cy, cz, r, t1, t0)  # swap θ0 ↔ θ1

        def _append_seg(result_cmds, seg, prev_end):
            """
            Append *seg* to *result_cmds*.  If the segment's start does not coincide
            with *prev_end*, insert a bevel lineTo to close the gap first.
            """
            sy, sz = _seg_start(seg)
            if prev_end is not None:
                py, pz = prev_end
                if abs(sy - py) > 1e-9 or abs(sz - pz) > 1e-9:
                    result_cmds.append(ShapeCommand("lineTo", y=sy, z=sz))
            result_cmds.extend(_seg_to_cmds(seg))
            return _seg_end(seg)

        # ---- build the two offset sides --------------------------------------
        left_segs = [_offset_seg(s, d_left) for s in segments]
        right_segs = [_offset_seg(s, d_right) for s in segments]

        # ---- assemble the closed profile ------------------------------------
        result: List[ShapeCommand] = []

        # Start: moveTo the beginning of the left-side path
        start_y, start_z = _seg_start(left_segs[0])
        result.append(ShapeCommand("moveTo", y=start_y, z=start_z))

        # Forward along the left side
        pen = (start_y, start_z)
        for seg in left_segs:
            pen = _append_seg(result, seg, pen)

        # End cap: bridge from end of left side to end of right side
        end_right_y, end_right_z = _seg_end(right_segs[-1])
        result.append(ShapeCommand("lineTo", y=end_right_y, z=end_right_z))

        # Backward along the right side (reversed)
        reversed_right = [_reverse_seg(s) for s in reversed(right_segs)]
        pen = (end_right_y, end_right_z)
        for seg in reversed_right:
            pen = _append_seg(result, seg, pen)

        # Start cap: closePath returns to the first moveTo point
        result.append(ShapeCommand("closePath"))

        return result

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
