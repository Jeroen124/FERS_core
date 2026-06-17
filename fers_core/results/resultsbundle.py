from __future__ import annotations

from dataclasses import field
from typing import Dict, Any, List, Mapping, Optional

from fers_core.results.member import MemberResult
from fers_core.results.plate import PlateResult
from fers_core.results.nodes import NodeDisplacement, NodeLocation, ReactionNodeResult, NodeForces
from fers_core.results.resultssummary import ResultsSummary
from fers_core.results.singleresults import SingleResults


def _to_plain(value: Any) -> Any:
    """Convert a pydantic model (or list/dict of them) to plain dicts."""
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    if isinstance(value, list):
        return [_to_plain(v) for v in value]
    if isinstance(value, dict):
        return {k: _to_plain(v) for k, v in value.items()}
    return value


class ResultsBundle:
    loadcases: Dict[str, SingleResults] = field(default_factory=dict)
    loadcombinations: Dict[str, SingleResults] = field(default_factory=dict)
    # Unity-check results: one entry per check definition (see the solver's
    # `UnityCheckResult` — utilization, status colour, per-entity + governing).
    unity_check_results: List[Dict[str, Any]] = field(default_factory=list)
    # Single consolidated HTML report, when the solver was asked to embed it.
    report_html: Optional[str] = None
    # Optional eigenvalue / seismic analysis results (plain dicts mirroring the
    # solver's ModalResults / BucklingResults / SeismicResults). Present only
    # when the matching `analysis.{modal,buckling,seismic}` block was requested.
    modal: Optional[Dict[str, Any]] = None
    buckling: Optional[Dict[str, Any]] = None
    seismic: Optional[Dict[str, Any]] = None

    # Factory from the generated Pydantic ResultsBundle
    @classmethod
    def from_pydantic(cls, pyd_bundle: Any) -> "ResultsBundle":
        lc_map: Dict[str, SingleResults] = {}
        for key, pyd_res in (getattr(pyd_bundle, "loadcases", {}) or {}).items():
            lc_map[str(key)] = SingleResults.from_pydantic(pyd_res)

        comb_map: Dict[str, SingleResults] = {}
        for key, pyd_res in (getattr(pyd_bundle, "loadcombinations", {}) or {}).items():
            comb_map[str(key)] = SingleResults.from_pydantic(pyd_res)

        instance = cls()
        instance.loadcases = lc_map
        instance.loadcombinations = comb_map
        instance.unity_check_results = _to_plain(getattr(pyd_bundle, "unity_check_results", []) or [])
        instance.report_html = getattr(pyd_bundle, "report_html", None)
        instance.modal = _to_plain(getattr(pyd_bundle, "modal", None))
        instance.buckling = _to_plain(getattr(pyd_bundle, "buckling", None))
        instance.seismic = _to_plain(getattr(pyd_bundle, "seismic", None))

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
                plate_results={
                    str(k): PlateResult.from_dict(v)
                    for k, v in (value.get("plate_results") or {}).items()
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
                plate_results={
                    str(k): PlateResult.from_dict(v)
                    for k, v in (value.get("plate_results") or {}).items()
                },
                summary=ResultsSummary(**(value.get("summary") or {})) if value.get("summary") else None,
                result_type=value.get("result_type"),
                unity_checks=value.get("unity_checks"),
            )

        instance = cls()
        instance.loadcases = lc_map
        instance.loadcombinations = comb_map
        instance.unity_check_results = list(raw.get("unity_check_results") or [])
        instance.report_html = raw.get("report_html")
        instance.modal = raw.get("modal")
        instance.buckling = raw.get("buckling")
        instance.seismic = raw.get("seismic")
        return instance

    def to_dict(self) -> Dict[str, Any]:
        return {
            "loadcases": {k: v.to_dict() for k, v in self.loadcases.items()},
            "loadcombinations": {k: v.to_dict() for k, v in self.loadcombinations.items()},
            "unity_check_results": self.unity_check_results,
            "report_html": self.report_html,
            "modal": self.modal,
            "buckling": self.buckling,
            "seismic": self.seismic,
        }
