from __future__ import annotations

from typing import Optional

from .releaseaxes import ReleaseAxes


class ScissorHinge:
    """How a member set connects to the members it crosses: as one continuous
    beam that moves relative to them along and about chosen axes.

    Give it to a :class:`MemberSet` (``MemberSet(..., scissor_hinge=...)``). At
    every node where a member of the set meets a member outside the set, or a
    plate (or only at the set's ``scissor_hinge_nodes``), the set's members stay
    joined to each other and move relative to the node along and about the
    released axes. A rail running over beams and resting on each one is the
    typical case::

        rail = MemberSet(
            members=[rail_1, rail_2],
            scissor_hinge=ScissorHinge(rotational_release_y=0.0, rotational_release_z=0.0),
        )

    Each value works as a ``MemberHinge`` release does: ``None`` holds that
    translation or rotation, ``0.0`` frees it, and a positive value is a linear
    spring between the set and the node, in force per length for a translation
    and moment per radian for a rotation (model units). A rail that may also
    slide along the beams frees that translation too.

    The axes are global X, Y and Z unless ``axes`` names a frame of your own
    (:meth:`ReleaseAxes.user`), as for a rack turned in plan. Not
    ``ReleaseAxes.LOCAL``: the members of a set need not share one frame.

    Nothing is released where the set's members meet only each other, or only a
    support; a support or nodal load at a released node acts on the node, which
    means on the members outside the set. A node's reported displacement is
    theirs, and the set's own motion there is in its members' end
    displacements. Where two sets that both carry a scissor hinge cross with
    nothing else, everything either set releases is free between them. A set of
    one member gives a release about the hinge's axes at that member's ends.

    Requires ``fers_calculations >= 0.2.68``. A model that uses one is written
    with ``schema_version`` 3, so an older solver refuses it instead of solving
    the connections as rigid.

    Args:
        rotational_release_x: Rotation about the first axis (global X).
        rotational_release_y: Rotation about the second axis (global Y).
        rotational_release_z: Rotation about the third axis (global Z).
        translational_release_x: Translation along the first axis (global X).
        translational_release_y: Translation along the second axis (global Y).
        translational_release_z: Translation along the third axis (global Z).
        axes: ``ReleaseAxes.GLOBAL`` (the default) or ``ReleaseAxes.user(x, y)``.
        id: Assigned from a counter when omitted.
    """

    _scissor_hinge_counter = 1

    def __init__(
        self,
        rotational_release_x: Optional[float] = None,
        rotational_release_y: Optional[float] = None,
        rotational_release_z: Optional[float] = None,
        id: Optional[int] = None,
        translational_release_x: Optional[float] = None,
        translational_release_y: Optional[float] = None,
        translational_release_z: Optional[float] = None,
        axes: ReleaseAxes = ReleaseAxes.GLOBAL,
    ):
        if id is None:
            self.id = ScissorHinge._scissor_hinge_counter
            ScissorHinge._scissor_hinge_counter += 1
        else:
            self.id = id
        self.rotational_release_x = rotational_release_x
        self.rotational_release_y = rotational_release_y
        self.rotational_release_z = rotational_release_z
        self.translational_release_x = translational_release_x
        self.translational_release_y = translational_release_y
        self.translational_release_z = translational_release_z
        self.axes = axes

    @classmethod
    def reset_counter(cls):
        cls._scissor_hinge_counter = 1

    def to_dict(self) -> dict:
        data = {"id": self.id}
        # Only what is set: an omitted axis is held, and the solver writes it back that way.
        if self.axes != ReleaseAxes.GLOBAL:
            data["axes"] = self.axes.to_dict()
        for kind in ("translational", "rotational"):
            for axis in ("x", "y", "z"):
                value = getattr(self, f"{kind}_release_{axis}")
                if value is not None:
                    data[f"{kind}_release_{axis}"] = value
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "ScissorHinge":
        return cls(
            rotational_release_x=data.get("rotational_release_x"),
            rotational_release_y=data.get("rotational_release_y"),
            rotational_release_z=data.get("rotational_release_z"),
            translational_release_x=data.get("translational_release_x"),
            translational_release_y=data.get("translational_release_y"),
            translational_release_z=data.get("translational_release_z"),
            axes=ReleaseAxes.from_dict(data.get("axes"), ReleaseAxes.GLOBAL),
            id=data.get("id"),
        )

    def __repr__(self) -> str:
        return f"ScissorHinge({self.to_dict()!r})"
