from __future__ import annotations

from dataclasses import field
from typing import Dict, Any, Mapping, Optional

from fers_core.results.member import MemberResult
from fers_core.results.nodes import NodeDisplacement, NodeLocation, ReactionNodeResult, NodeForces
from fers_core.results.resultssummary import ResultsSummary
from fers_core.results.singleresults import SingleResults


class ResultsBundle:
    loadcases: Dict[str, SingleResults] = field(default_factory=dict)
    loadcombinations: Dict[str, SingleResults] = field(default_factory=dict)
    unity_checks_overview: Optional[Dict[str, Any]] = None

    # Factory from the generated Pydantic ResultsBundle
    @classmethod
    def from_pydantic(cls, pyd_bundle: Any) -> "ResultsBundle":
        lc_map: Dict[str, SingleResults] = {}
        for key, pyd_res in (getattr(pyd_bundle, "loadcases", {}) or {}).items():
            lc_map[str(key)] = SingleResults.from_pydantic(pyd_res)

        comb_map: Dict[str, SingleResults] = {}
        for key, pyd_res in (getattr(pyd_bundle, "loadcombinations", {}) or {}).items():
            comb_map[str(key)] = SingleResults.from_pydantic(pyd_res)

        overview_value = getattr(pyd_bundle, "unity_checks_overview", None)
        if hasattr(overview_value, "model_dump"):
            overview_value = overview_value.model_dump()  # type: ignore[attr-defined]
        elif hasattr(overview_value, "dict"):
            overview_value = overview_value.dict()  # type: ignore[attr-defined]

        instance = cls()
        instance.loadcases = lc_map
        instance.loadcombinations = comb_map
        instance.unity_checks_overview = overview_value

        return instance

    # Optional factory from already-parsed dicts (e.g., raw JSON)
    @classmethod
    def from_raw_dict(cls, raw: Mapping[str, Any]) -> "ResultsBundle":
        lc_map: Dict[str, SingleResults] = {}
        for key, value in (raw.get("loadcases") or {}).items():
            lc_map[str(key)] = SingleResults(
                name=str(value.get("name", "")),
                displacement_nodes={
                    str(k): NodeDisplacement(**v) for k, v in (value.get("displacement_nodes") or {}).items()
                },
                reaction_nodes={
                    str(k): ReactionNodeResult(
                        location=NodeLocation(**v.get("location", {})),
                        nodal_forces=NodeForces(**v.get("nodal_forces", {})),
                        support_id=int(v.get("support_id", 0)),
                    )
                    for k, v in (value.get("reaction_nodes") or {}).items()
                },
                member_results={
                    str(k): MemberResult(
                        start_node_forces=NodeForces(**v.get("start_node_forces", {})),
                        end_node_forces=NodeForces(**v.get("end_node_forces", {})),
                        maximums=NodeForces(**v.get("maximums", {})),
                        minimums=NodeForces(**v.get("minimums", {})),
                    )
                    for k, v in (value.get("member_results") or {}).items()
                },
                summary=ResultsSummary(**(value.get("summary") or {})) if value.get("summary") else None,
                result_type=value.get("result_type"),
                unity_checks=value.get("unity_checks"),
            )

        comb_map: Dict[str, SingleResults] = {}
        for key, value in (raw.get("loadcombinations") or {}).items():
            comb_map[str(key)] = SingleResults(
                name=str(value.get("name", "")),
                displacement_nodes={
                    str(k): NodeDisplacement(**v) for k, v in (value.get("displacement_nodes") or {}).items()
                },
                reaction_nodes={
                    str(k): ReactionNodeResult(
                        location=NodeLocation(**v.get("location", {})),
                        nodal_forces=NodeForces(**v.get("nodal_forces", {})),
                        support_id=int(v.get("support_id", 0)),
                    )
                    for k, v in (value.get("reaction_nodes") or {}).items()
                },
                member_results={
                    str(k): MemberResult(
                        start_node_forces=NodeForces(**v.get("start_node_forces", {})),
                        end_node_forces=NodeForces(**v.get("end_node_forces", {})),
                        maximums=NodeForces(**v.get("maximums", {})),
                        minimums=NodeForces(**v.get("minimums", {})),
                    )
                    for k, v in (value.get("member_results") or {}).items()
                },
                summary=ResultsSummary(**(value.get("summary") or {})) if value.get("summary") else None,
                result_type=value.get("result_type"),
                unity_checks=value.get("unity_checks"),
            )

        return cls(
            loadcases=lc_map,
            loadcombinations=comb_map,
            unity_checks_overview=raw.get("unity_checks_overview"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "loadcases": {k: v.to_dict() for k, v in self.loadcases.items()},
            "loadcombinations": {k: v.to_dict() for k, v in self.loadcombinations.items()},
            "unity_checks_overview": self.unity_checks_overview,
        }
