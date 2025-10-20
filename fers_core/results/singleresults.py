from __future__ import annotations

from dataclasses import field
from typing import Dict, Any, Optional

from fers_core.results.member import MemberResult
from fers_core.results.nodes import NodeDisplacement, ReactionNodeResult
from fers_core.results.resultssummary import ResultsSummary


class SingleResults:
    name: str
    displacement_nodes: Dict[str, NodeDisplacement] = field(default_factory=dict)
    reaction_nodes: Dict[str, ReactionNodeResult] = field(default_factory=dict)
    member_results: Dict[str, MemberResult] = field(default_factory=dict)
    summary: Optional[ResultsSummary] = None
    result_type: Optional[Dict[str, Any]] = None
    unity_checks: Optional[Dict[str, Any]] = None

    @classmethod
    def from_pydantic(cls, pyd_results: Any) -> "SingleResults":
        name_value = getattr(pyd_results, "name", None)
        displacement_map: Dict[str, NodeDisplacement] = {}
        for key, value in (getattr(pyd_results, "displacement_nodes", {}) or {}).items():
            displacement_map[str(key)] = NodeDisplacement.from_pydantic(value)

        reaction_map: Dict[str, ReactionNodeResult] = {}
        for key, value in (getattr(pyd_results, "reaction_nodes", {}) or {}).items():
            reaction_map[str(key)] = ReactionNodeResult.from_pydantic(value)

        member_map: Dict[str, MemberResult] = {}
        for key, value in (getattr(pyd_results, "member_results", {}) or {}).items():
            member_map[str(key)] = MemberResult.from_pydantic(value)

        summary_pyd = getattr(pyd_results, "summary", None)
        summary_ = ResultsSummary.from_pydantic(summary_pyd) if summary_pyd else None

        # result_type can be ResultType RootModel; store as a plain dict for stability
        result_type_pyd = getattr(pyd_results, "result_type", None)
        result_type_dict: Optional[Dict[str, Any]] = None
        if result_type_pyd is not None:
            # tolerant try: pydantic v1 has .dict(), v2 has .model_dump(), RootModel has .root
            try:
                result_type_dict = (
                    result_type_pyd.model_dump()  # type: ignore[attr-defined]
                    if hasattr(result_type_pyd, "model_dump")
                    else result_type_pyd.dict()  # type: ignore[attr-defined]
                )
            except Exception:
                result_type_dict = {"value": getattr(result_type_pyd, "root", None)}

        unity_checks_value = getattr(pyd_results, "unity_checks", None)
        if hasattr(unity_checks_value, "model_dump"):
            unity_checks_value = unity_checks_value.model_dump()  # type: ignore[attr-defined]
        elif hasattr(unity_checks_value, "dict"):
            unity_checks_value = unity_checks_value.dict()  # type: ignore[attr-defined]

        instance = cls()
        instance.name = name_value if name_value is not None else ""
        instance.displacement_nodes = displacement_map
        instance.reaction_nodes = reaction_map
        instance.member_results = member_map
        instance.summary = summary_
        instance.result_type = result_type_dict
        instance.unity_checks = unity_checks_value
        return instance

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "displacement_nodes": {k: v.to_dict() for k, v in self.displacement_nodes.items()},
            "reaction_nodes": {k: v.to_dict() for k, v in self.reaction_nodes.items()},
            "member_results": {k: v.to_dict() for k, v in self.member_results.items()},
            "summary": self.summary.to_dict() if self.summary else None,
            "result_type": self.result_type,
            "unity_checks": self.unity_checks,
        }
