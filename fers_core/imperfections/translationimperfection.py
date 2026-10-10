from typing import Any

from fers_core.types.list_utils import as_list
from ..members.memberset import MemberSet


class TranslationImperfection:
    def __init__(
        self,
        memberset: list[MemberSet],
        magnitude: float,
        axis: tuple,
    ):
        """
        Initialize a translational imperfection of one or more member sets.

        Each set's nodes are displaced along ``axis``, growing linearly from zero
        at the set's base node to ``magnitude`` at its farthest node. Which load
        combinations receive it is set on the owning ``ImperfectionCase``.

        Args:
            memberset (list[MemberSet]): The member sets to displace.
            magnitude (float): The displacement at the farthest node, in the
                model's length unit.
            axis (tuple): The direction of the displacement (e.g. (1, 0, 0) for X).
        """
        self.memberset = memberset
        self.magnitude = magnitude
        self.axis = axis

    def to_dict(self):
        return {
            "memberset_ids": [ms.id for ms in self.memberset],
            "magnitude": self.magnitude,
            "axis": self.axis,
        }

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        *,
        membersets_by_id: dict[int, MemberSet],
    ) -> "TranslationImperfection":
        """
        data schema (the solver's):
        {
            "memberset_ids": [1, 2],
            "magnitude": 0.01,
            "axis": [0, 1, 0]
        }

        Documents written before 0.1.98 name the sets "memberset" (or
        "membersets"); those keys are still read.
        """

        # Resolve member sets
        ms_ids = as_list(
            data.get("memberset_ids") or data.get("memberset") or data.get("membersets"),
            "memberset_ids",
        )
        if not ms_ids:
            raise ValueError("TranslationImperfection.from_dict: 'memberset_ids' list is required.")

        membersets: list[MemberSet] = []
        for ms_id in ms_ids:
            ms = membersets_by_id.get(ms_id)
            if ms is None:
                # Skip member sets that don't exist in this model configuration.
                continue
            membersets.append(ms)

        magnitude = float(data.get("magnitude", 0.0))
        axis_raw = data.get("axis", (0.0, 0.0, 0.0))
        axis = tuple(axis_raw) if isinstance(axis_raw, (list, tuple)) else tuple(float(x) for x in axis_raw)

        return cls(memberset=membersets, magnitude=magnitude, axis=axis)
