from __future__ import annotations

from typing import Optional


class ScissorHinge:
    """How a member set connects to the members it crosses: as one continuous
    beam that turns relative to them about global axes.

    Give it to a :class:`MemberSet` (``MemberSet(..., scissor_hinge=...)``). At
    every node where a member of the set meets a member outside the set, or a
    plate, the set's members stay joined to each other, keep the node's
    translations, and turn relative to the node about the released axes. A rail
    running over beams and resting on each one is the typical case::

        rail = MemberSet(
            members=[rail_1, rail_2],
            scissor_hinge=ScissorHinge(rotational_release_y=0.0, rotational_release_z=0.0),
        )

    Each rotation is about a global axis and works as a ``MemberHinge`` release
    does: ``None`` holds it, ``0.0`` frees it, and a positive value is a linear
    rotational spring between the set and the node, in moment per radian (model
    units).

    Nothing is released where the set's members meet only each other, or only a
    support; a support or nodal load at a released node acts on the node, which
    means on the members outside the set. A node's reported rotation is theirs,
    and the set's own rotation there is in its members' end displacements.
    Where two sets that both carry a scissor hinge cross with nothing else,
    every axis either set releases is free between them. A set of one member
    gives a release about global axes at that member's ends.

    Requires ``fers_calculations >= 0.2.68``. A model that uses one is written
    with ``schema_version`` 3, so an older solver refuses it instead of solving
    the connections as rigid.

    Args:
        rotational_release_x: Rotation about global X.
        rotational_release_y: Rotation about global Y.
        rotational_release_z: Rotation about global Z.
        id: Assigned from a counter when omitted.
    """

    _scissor_hinge_counter = 1

    def __init__(
        self,
        rotational_release_x: Optional[float] = None,
        rotational_release_y: Optional[float] = None,
        rotational_release_z: Optional[float] = None,
        id: Optional[int] = None,
    ):
        if id is None:
            self.id = ScissorHinge._scissor_hinge_counter
            ScissorHinge._scissor_hinge_counter += 1
        else:
            self.id = id
        self.rotational_release_x = rotational_release_x
        self.rotational_release_y = rotational_release_y
        self.rotational_release_z = rotational_release_z

    @classmethod
    def reset_counter(cls):
        cls._scissor_hinge_counter = 1

    def to_dict(self) -> dict:
        data = {"id": self.id}
        # Only what is set: an omitted axis is held, and the solver writes it back that way.
        for axis in ("x", "y", "z"):
            value = getattr(self, f"rotational_release_{axis}")
            if value is not None:
                data[f"rotational_release_{axis}"] = value
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "ScissorHinge":
        return cls(
            rotational_release_x=data.get("rotational_release_x"),
            rotational_release_y=data.get("rotational_release_y"),
            rotational_release_z=data.get("rotational_release_z"),
            id=data.get("id"),
        )

    def __repr__(self) -> str:
        return f"ScissorHinge({self.to_dict()!r})"
