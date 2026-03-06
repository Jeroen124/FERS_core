"""
807 — Custom Line Stroke (Path Extrusion)
==========================================
Demonstrates how to draw a custom open path and extrude it into a closed
filled cross-section using ``ShapePath.stroke_path()``.

Key features shown:
  • Drawing an open path with ``moveTo``, ``lineTo`` and ``arcTo``
  • ``ShapePath.stroke_path(commands, thickness, offset)``
      – offset="center"  the drawn path is the centreline  (±t/2 each side)
      – offset="left"    the drawn path is the right edge  (shape grows left)
      – offset="right"   the drawn path is the left edge   (shape grows right)
  • For straight segments the offset is a parallel shift perpendicular to
    the travel direction.
  • For arc segments the centre and sweep angles are kept identical; only
    the radius changes (outer arc r+d, inner arc r-d), so a curved strip
    of uniform thickness is produced with the correct concentric geometry.
  • Using a stroked profile as the geometry for a ``Section``
"""

import math
from fers_core import ShapePath, Section, Material
from fers_core.members.shapecommand import ShapeCommand

# =============================================================================
# Step 1: Material
# =============================================================================
steel = Material(name="S355", e_mod=210e9, g_mod=81e9, density=7850, yield_stress=355e6)


# =============================================================================
# Step 2: Draw some open paths
# =============================================================================

# --- 2a: A simple horizontal straight line (100 mm long) ---------------------
#
#          z →
#          ──────────────
#   y ↑   (y=0, z=0)  (y=0, z=100mm)
#
line_path = [
    ShapeCommand("moveTo", y=0.0, z=-0.050),
    ShapeCommand("lineTo", y=0.0, z=+0.050),
]

# --- 2b: An L-shaped path (two line segments meeting at a corner) ------------
#
#   Start at bottom-left, go right then up.
#
l_path = [
    ShapeCommand("moveTo", y=-0.050, z=-0.050),
    ShapeCommand("lineTo", y=-0.050, z=+0.050),  # horizontal leg
    ShapeCommand("lineTo", y=+0.050, z=+0.050),  # vertical leg
]

# --- 2c: A curved arc path (quarter circle, r = 75 mm) ----------------------
#
#  Arc convention:  z(θ) = cz + r·sin(θ),  y(θ) = cy + r·cos(θ)
#  Increasing θ sweeps clockwise in the yz-plane.
#  Quarter from top (θ=0) to right (θ=π/2).
#
R = 0.075  # 75 mm radius
arc_path = [ShapeCommand("moveTo", y=R, z=0.0)]
arc_path += ShapePath.arc_center_angles(center_y=0.0, center_z=0.0, radius=R, theta0=0.0, theta1=math.pi / 2)

# --- 2d: A mixed path: straight line + arc (like a lollipop stick + curve) --
#
#  Straight section along z, then a quarter-circle arc upward.
#
mixed_path = [
    ShapeCommand("moveTo", y=0.0, z=-0.050),
    ShapeCommand("lineTo", y=0.0, z=+0.025),  # straight 75 mm
]
mixed_path += ShapePath.arc_center_angles(
    center_y=0.025, center_z=0.025, radius=0.025, theta0=-math.pi / 2, theta1=0.0
)


# =============================================================================
# Step 3: Extrude each path with stroke_path
# =============================================================================
THICKNESS = 0.010  # 10 mm wall thickness

# --- offset modes demonstrated on the straight line ---
line_center = ShapePath(
    name="Line – center",
    shape_commands=ShapePath.stroke_path(line_path, thickness=THICKNESS, offset="center"),
)
line_left = ShapePath(
    name="Line – left",
    shape_commands=ShapePath.stroke_path(line_path, thickness=THICKNESS, offset="left"),
)
line_right = ShapePath(
    name="Line – right",
    shape_commands=ShapePath.stroke_path(line_path, thickness=THICKNESS, offset="right"),
)

# --- L-shaped strip, centred ---
l_strip = ShapePath(
    name="L-path strip – center",
    shape_commands=ShapePath.stroke_path(l_path, thickness=THICKNESS, offset="center"),
)

# --- Curved arc strip: outer r = R + t/2, inner r = R − t/2 ---
arc_strip = ShapePath(
    name="Arc strip – center",
    shape_commands=ShapePath.stroke_path(arc_path, thickness=THICKNESS, offset="center"),
)

# --- Mixed straight + arc, centred ---
mixed_strip = ShapePath(
    name="Mixed strip – center",
    shape_commands=ShapePath.stroke_path(mixed_path, thickness=THICKNESS, offset="center"),
)


# =============================================================================
# Step 4: Print a summary of generated commands
# =============================================================================
profiles = [line_center, line_left, line_right, l_strip, arc_strip, mixed_strip]

print(f"\n{'Profile':<30s}  {'Commands':>8s}  {'Types'}")
print("-" * 70)
for p in profiles:
    cmd_types = ", ".join(dict.fromkeys(c.command for c in p.shape_commands))
    print(f"{p.name:<30s}  {len(p.shape_commands):8d}  {cmd_types}")


# =============================================================================
# Step 5: Wrap a stroked arc strip as a Section (manual properties)
# =============================================================================
# Section properties for a curved flat bar (approximate, for illustration).
# Replace with values from sectionproperties or hand calculations.
t = THICKNESS
b_flat = R * (math.pi / 2)  # arc length of centreline ≈ flat bar width
area_approx = b_flat * t
i_y_approx = b_flat * t**3 / 12
i_z_approx = t * b_flat**3 / 12
j_approx = b_flat * t**3 / 3

arc_section = Section(
    name="Curved flat bar R75 t10",
    material=steel,
    area=area_approx,
    i_y=i_y_approx,
    i_z=i_z_approx,
    j=j_approx,
    shape_path=arc_strip,
)
print(f"\nSection '{arc_section.name}'")
print(f"  A  = {arc_section.area * 1e4:.2f} cm²")
print(f"  Iy = {arc_section.i_y * 1e8:.4f} cm⁴")
print(f"  Iz = {arc_section.i_z * 1e8:.4f} cm⁴")
print(f"  J  = {arc_section.j * 1e8:.4f} cm⁴")


# =============================================================================
# Step 6 (optional): Plot cross-sections
# =============================================================================
# Uncomment any line below to visualise the profile:
#
# line_center.plot()
# line_left.plot()
# line_right.plot()
# l_strip.plot()
# arc_strip.plot()
# mixed_strip.plot()
