"""
Tests for ShapePath.stroke_path()
===================================
All tests are purely geometric — no solver or FEM dependency.

Coordinate convention (same as ShapePath / arc_center_angles):
    z(θ) = center_z + r·sin(θ)
    y(θ) = center_y + r·cos(θ)

Left-of-travel-direction offset:
    • Straight line: shift perpendicular in the +left-normal direction.
    • Arc (increasing θ, CW sweep): left = outward → r_new = r + d
    • Arc (decreasing θ, CCW sweep): left = inward  → r_new = r - d
"""

import math
import pytest

from fers_core.members.shapepath import ShapePath
from fers_core.members.shapecommand import ShapeCommand


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cmds(offset, thickness=0.010):
    """Return stroke_path result for a horizontal line at y=0, z=0→0.1."""
    path = [
        ShapeCommand("moveTo", y=0.0, z=0.0),
        ShapeCommand("lineTo", y=0.0, z=0.100),
    ]
    return ShapePath.stroke_path(path, thickness=thickness, offset=offset)


def _arc_cmds(r, thickness, offset, theta0=0.0, theta1=math.pi / 2):
    """Return stroke_path result for a quarter-arc at the origin."""
    path = [ShapeCommand("moveTo", y=r, z=0.0)]
    path += ShapePath.arc_center_angles(0.0, 0.0, r, theta0, theta1)
    return ShapePath.stroke_path(path, thickness=thickness, offset=offset)


def _commands_sequence(cmds):
    return [c.command for c in cmds]


def approx(v, rel=1e-9):
    return pytest.approx(v, rel=rel, abs=1e-12)


# ---------------------------------------------------------------------------
# 1. Output structure — every result must start with moveTo / end with closePath
# ---------------------------------------------------------------------------


class TestOutputStructure:
    def test_starts_with_moveto(self):
        cmds = _cmds("center")
        assert cmds[0].command == "moveTo"

    def test_ends_with_closepath(self):
        cmds = _cmds("center")
        assert cmds[-1].command == "closePath"

    def test_no_consecutive_moveto(self):
        cmds = _cmds("center")
        for a, b in zip(cmds, cmds[1:]):
            assert not (a.command == "moveTo" and b.command == "moveTo")

    def test_empty_input_returns_empty(self):
        result = ShapePath.stroke_path([], thickness=0.010, offset="center")
        assert result == []

    def test_invalid_offset_raises(self):
        path = [ShapeCommand("moveTo", y=0.0, z=0.0), ShapeCommand("lineTo", y=0.0, z=1.0)]
        with pytest.raises(ValueError, match="offset"):
            ShapePath.stroke_path(path, thickness=0.010, offset="diagonal")


# ---------------------------------------------------------------------------
# 2. Straight-line strokes — exact coordinate checks
#
#  Path: y=0, z=0 → y=0, z=100 mm  (travel direction = +z)
#  Left normal = +y direction.
# ---------------------------------------------------------------------------


class TestStraightLineStroke:
    T = 0.010  # 10 mm

    # ---- center offset ----

    def test_center_command_sequence(self):
        assert _commands_sequence(_cmds("center")) == ["moveTo", "lineTo", "lineTo", "lineTo", "closePath"]

    def test_center_left_side_y_offset(self):
        cmds = _cmds("center")
        # moveTo and first lineTo should be at y = +T/2
        assert cmds[0].y == approx(+self.T / 2)
        assert cmds[1].y == approx(+self.T / 2)

    def test_center_right_side_y_offset(self):
        cmds = _cmds("center")
        # the two right-side points should be at y = -T/2
        assert cmds[2].y == approx(-self.T / 2)
        assert cmds[3].y == approx(-self.T / 2)

    def test_center_z_extents(self):
        cmds = _cmds("center")
        z_vals = [c.z for c in cmds if c.z is not None]
        assert min(z_vals) == approx(0.0)
        assert max(z_vals) == approx(0.100)

    # ---- left offset (original path = right edge) ----

    def test_left_right_edge_at_y_zero(self):
        cmds = _cmds("left")
        # Right side (reversed, last two lineTo before closePath) must be at y=0
        line_cmds = [c for c in cmds if c.command in ("moveTo", "lineTo")]
        right_side_y = {c.y for c in line_cmds if c.y is not None and abs(c.y) < 1e-9}
        assert len(right_side_y) >= 1  # at least one point on y=0

    def test_left_left_edge_at_y_T(self):
        cmds = _cmds("left")
        # Left side must be at y = +T
        line_cmds = [c for c in cmds if c.command in ("moveTo", "lineTo")]
        assert any(abs(c.y - self.T) < 1e-9 for c in line_cmds if c.y is not None)

    # ---- right offset (original path = left edge) ----

    def test_right_left_edge_at_y_zero(self):
        cmds = _cmds("right")
        line_cmds = [c for c in cmds if c.command in ("moveTo", "lineTo")]
        assert any(abs(c.y) < 1e-9 for c in line_cmds if c.y is not None)

    def test_right_right_edge_at_minus_T(self):
        cmds = _cmds("right")
        line_cmds = [c for c in cmds if c.command in ("moveTo", "lineTo")]
        assert any(abs(c.y - (-self.T)) < 1e-9 for c in line_cmds if c.y is not None)

    # ---- thickness is symmetric for center ----

    def test_center_total_width_equals_thickness(self):
        cmds = _cmds("center")
        y_vals = [c.y for c in cmds if c.y is not None]
        assert max(y_vals) - min(y_vals) == approx(self.T)

    def test_left_total_width_equals_thickness(self):
        cmds = _cmds("left")
        y_vals = [c.y for c in cmds if c.y is not None]
        assert max(y_vals) - min(y_vals) == approx(self.T)

    def test_right_total_width_equals_thickness(self):
        cmds = _cmds("right")
        y_vals = [c.y for c in cmds if c.y is not None]
        assert max(y_vals) - min(y_vals) == approx(self.T)


# ---------------------------------------------------------------------------
# 3. Arc strokes — radius checks
#
#  Quarter-circle arc, center at origin, r = 75 mm, θ: 0 → π/2 (CW sweep).
#  Left = outward.
# ---------------------------------------------------------------------------


class TestArcStroke:
    R = 0.075
    T = 0.010

    def _arc_radii(self, offset):
        """Return the two arc radii present in the stroked result."""
        cmds = _arc_cmds(self.R, self.T, offset)
        return [c.r for c in cmds if c.command == "arcTo"]

    def test_center_has_two_arcs(self):
        radii = self._arc_radii("center")
        assert len(radii) == 2

    def test_center_outer_radius(self):
        radii = self._arc_radii("center")
        assert max(radii) == approx(self.R + self.T / 2)

    def test_center_inner_radius(self):
        radii = self._arc_radii("center")
        assert min(radii) == approx(self.R - self.T / 2)

    def test_left_outer_radius(self):
        radii = self._arc_radii("left")
        assert max(radii) == approx(self.R + self.T)

    def test_left_inner_radius_equals_R(self):
        # left offset: right side d=0, so inner arc keeps original radius
        radii = self._arc_radii("left")
        assert min(radii) == approx(self.R)

    def test_right_outer_radius_equals_R(self):
        # right offset: left side d=0, so outer arc keeps original radius
        radii = self._arc_radii("right")
        assert max(radii) == approx(self.R)

    def test_right_inner_radius(self):
        radii = self._arc_radii("right")
        assert min(radii) == approx(self.R - self.T)

    def test_arc_centers_unchanged(self):
        cmds = _arc_cmds(self.R, self.T, "center")
        for c in cmds:
            if c.command == "arcTo":
                assert c.center_y == approx(0.0)
                assert c.center_z == approx(0.0)

    def test_arc_sweep_angles_preserved(self):
        cmds = _arc_cmds(self.R, self.T, "center")
        arcs = [c for c in cmds if c.command == "arcTo"]
        # Forward arc: theta0=0, theta1=pi/2
        # Backward arc: theta0=pi/2, theta1=0
        sweeps = {(round(c.theta0, 6), round(c.theta1, 6)) for c in arcs}
        assert (0.0, round(math.pi / 2, 6)) in sweeps
        assert (round(math.pi / 2, 6), 0.0) in sweeps

    def test_arc_radius_collapse_raises(self):
        """Thickness larger than radius on the inner side must raise ValueError."""
        with pytest.raises(ValueError, match="radius"):
            _arc_cmds(self.R, thickness=self.R + 0.001, offset="right")

    def test_decreasing_theta_arc_left_is_inner(self):
        """For a CCW arc (decreasing θ) the left offset shrinks the radius."""
        r = 0.050
        t = 0.008
        cmds = _arc_cmds(r, t, "center", theta0=math.pi / 2, theta1=0.0)
        radii = [c.r for c in cmds if c.command == "arcTo"]
        assert len(radii) == 2
        # For decreasing theta: left = inward → r_new = r - d_left = r - t/2
        # right side d_right is negative: r_new = r - d_right = r + t/2
        assert min(radii) == approx(r - t / 2)
        assert max(radii) == approx(r + t / 2)


# ---------------------------------------------------------------------------
# 4. L-shaped path (two line segments) — bevel join check
# ---------------------------------------------------------------------------


class TestLShapedStroke:
    def _l_stroke(self, offset="center", thickness=0.010):
        path = [
            ShapeCommand("moveTo", y=-0.050, z=-0.050),
            ShapeCommand("lineTo", y=-0.050, z=+0.050),
            ShapeCommand("lineTo", y=+0.050, z=+0.050),
        ]
        return ShapePath.stroke_path(path, thickness=thickness, offset=offset)

    def test_has_two_lineto_segments_on_each_side(self):
        cmds = self._l_stroke()
        line_tos = [c for c in cmds if c.command == "lineTo"]
        # 2 left segments + end cap + 2 right segments (reversed) + bevel joins
        assert len(line_tos) >= 5

    def test_starts_and_ends_correctly(self):
        cmds = self._l_stroke()
        assert cmds[0].command == "moveTo"
        assert cmds[-1].command == "closePath"

    def test_contains_no_arcs(self):
        cmds = self._l_stroke()
        assert not any(c.command == "arcTo" for c in cmds)


# ---------------------------------------------------------------------------
# 5. Mixed path (line + arc)
# ---------------------------------------------------------------------------


class TestMixedStroke:
    def _mixed_stroke(self, thickness=0.010):
        path = [
            ShapeCommand("moveTo", y=0.0, z=-0.050),
            ShapeCommand("lineTo", y=0.0, z=+0.025),
        ]
        path += ShapePath.arc_center_angles(0.025, 0.025, 0.025, -math.pi / 2, 0.0)
        return ShapePath.stroke_path(path, thickness=thickness, offset="center")

    def test_contains_both_lineto_and_arcto(self):
        cmds = self._mixed_stroke()
        types = {c.command for c in cmds}
        assert "lineTo" in types
        assert "arcTo" in types

    def test_starts_and_ends_correctly(self):
        cmds = self._mixed_stroke()
        assert cmds[0].command == "moveTo"
        assert cmds[-1].command == "closePath"
