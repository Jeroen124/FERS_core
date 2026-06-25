"""ShapePath.to_dict()/from_dict() round-trip (feedback item 04).

Regression for the bug where ShapePath.from_dict() reassigned the loop variable
instead of appending, so the rebuilt ShapePath had an empty shape_commands list.
"""

from fers_core import ShapePath
from fers_core.members.shapecommand import ShapeCommand


def _demo_shapepath() -> ShapePath:
    return ShapePath(
        name="RHS-demo",
        shape_commands=[
            ShapeCommand("moveTo", y=0.0, z=0.0),
            ShapeCommand("lineTo", y=10.0, z=0.0),
            ShapeCommand("closePath"),
        ],
    )


def test_from_dict_preserves_shape_commands():
    sp = _demo_shapepath()
    d = sp.to_dict()
    sp2 = ShapePath.from_dict(d)

    assert len(d["shape_commands"]) == 3
    # The bug produced 0 here.
    assert len(sp2.shape_commands) == 3
    assert len(sp2.to_dict()["shape_commands"]) == 3


def test_round_trip_preserves_command_types_and_coords():
    sp = _demo_shapepath()
    sp2 = ShapePath.from_dict(sp.to_dict())

    commands = [(c.command, c.y, c.z) for c in sp.shape_commands]
    commands2 = [(c.command, c.y, c.z) for c in sp2.shape_commands]
    assert commands == commands2


def test_from_dict_empty_commands():
    sp = ShapePath.from_dict({"name": "empty", "shape_commands": []})
    assert sp.shape_commands == []
