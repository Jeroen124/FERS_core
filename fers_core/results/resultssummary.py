from __future__ import annotations

from typing import Dict, Any


class ResultsSummary:
    total_displacements: int = 0
    total_member_forces: int = 0
    total_reaction_forces: int = 0

    @classmethod
    def from_pydantic(cls, pyd_object: Any) -> "ResultsSummary":
        return cls(
            total_displacements=int(getattr(pyd_object, "total_displacements", 0) or 0),
            total_member_forces=int(getattr(pyd_object, "total_member_forces", 0) or 0),
            total_reaction_forces=int(getattr(pyd_object, "total_reaction_forces", 0) or 0),
        )

    def to_dict(self) -> Dict[str, int]:
        return {
            "total_displacements": self.total_displacements,
            "total_member_forces": self.total_member_forces,
            "total_reaction_forces": self.total_reaction_forces,
        }
