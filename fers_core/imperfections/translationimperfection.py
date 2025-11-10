from typing import Any

from fers_core.utils.list_utils import as_list
from ..members.memberset import MemberSet


class TranslationImperfection:
    def __init__(
        self,
        memberset: list[MemberSet],
        magnitude: float,
        axis: tuple,
    ):
        """
        Initialize a translation imperfection applied to a member.

        Args:
            member: The member to which the imperfection is applied.
            load_case: The LoadCase instance this imperfection is associated with.
            magnitude (float): The magnitude of the translation.
            direction (tuple): The direction of the translation (e.g., (1, 0, 0) for X-axis).
        """
        self.memberset = memberset
        self.magnitude = magnitude
        self.axis = axis

    def to_dict(self):
        return {
            "memberset": [ms.id for ms in self.memberset],
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
        data schema (typical):
        {
            "memberset": [1, 2],            # or "membersets"
            "magnitude": 0.01,
            "axis": [0, 1, 0]
        }
        """

        # Resolve member sets
        ms_ids = as_list(
            data.get("memberset") or data.get("membersets"),
            "memberset",
        )
        if not ms_ids:
            raise ValueError("TranslationImperfection.from_dict: 'memberset' list is required.")

        membersets: list[MemberSet] = []
        for ms_id in ms_ids:
            ms = membersets_by_id.get(ms_id)
            if ms is None:
                raise KeyError(f"TranslationImperfection.from_dict: MemberSet with id={ms_id} not found.")
            membersets.append(ms)

        magnitude = float(data.get("magnitude", 0.0))
        axis_raw = data.get("axis", (0.0, 0.0, 0.0))
        axis = tuple(axis_raw) if isinstance(axis_raw, (list, tuple)) else tuple(float(x) for x in axis_raw)

        return cls(memberset=membersets, magnitude=magnitude, axis=axis)
