from __future__ import annotations

from typing import Dict, Any, Optional

from fers_core.results.nodes import NodeForces


class MemberResult:
    def __init__(
        self,
        start_node_forces: Optional[NodeForces] = None,
        end_node_forces: Optional[NodeForces] = None,
        maximums: Optional[NodeForces] = None,
        minimums: Optional[NodeForces] = None,
    ) -> None:
        self.start_node_forces = start_node_forces if start_node_forces is not None else NodeForces()
        self.end_node_forces = end_node_forces if end_node_forces is not None else NodeForces()
        self.maximums = maximums if maximums is not None else NodeForces()
        self.minimums = minimums if minimums is not None else NodeForces()

    @classmethod
    def from_pydantic(cls, model_object: Any) -> "MemberResult":
        return cls(
            start_node_forces=NodeForces.from_pydantic(getattr(model_object, "start_node_forces", None)),
            end_node_forces=NodeForces.from_pydantic(getattr(model_object, "end_node_forces", None)),
            maximums=NodeForces.from_pydantic(getattr(model_object, "maximums", None)),
            minimums=NodeForces.from_pydantic(getattr(model_object, "minimums", None)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "start_node_forces": self.start_node_forces.to_dict(),
            "end_node_forces": self.end_node_forces.to_dict(),
            "maximums": self.maximums.to_dict(),
            "minimums": self.minimums.to_dict(),
        }
