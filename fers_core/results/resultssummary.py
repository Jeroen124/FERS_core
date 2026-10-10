from __future__ import annotations

from typing import Dict, Any, Mapping


class ResultsSummary:
    total_displacements: int = 0
    total_member_forces: int = 0
    total_reaction_forces: int = 0
    total_plate_forces: int = 0

    @classmethod
    def from_pydantic(cls, pyd_object: Any) -> "ResultsSummary":
        instance = cls()
        instance.total_displacements = getattr(pyd_object, "total_displacements", 0)
        instance.total_member_forces = getattr(pyd_object, "total_member_forces", 0)
        instance.total_reaction_forces = getattr(pyd_object, "total_reaction_forces", 0)
        instance.total_plate_forces = getattr(pyd_object, "total_plate_forces", 0)
        return instance

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ResultsSummary":
        instance = cls()
        instance.total_displacements = data.get("total_displacements", 0)
        instance.total_member_forces = data.get("total_member_forces", 0)
        instance.total_reaction_forces = data.get("total_reaction_forces", 0)
        # As from_pydantic: the schema lets this one be absent, and absent reads None.
        instance.total_plate_forces = data.get("total_plate_forces")
        return instance

    def to_dict(self) -> Dict[str, int]:
        return {
            "total_displacements": self.total_displacements,
            "total_member_forces": self.total_member_forces,
            "total_reaction_forces": self.total_reaction_forces,
            "total_plate_forces": self.total_plate_forces,
        }
