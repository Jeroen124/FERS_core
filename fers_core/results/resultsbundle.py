from __future__ import annotations

from dataclasses import dataclass, field
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


# A real dataclass, for the same reason as SingleResults: these annotations
# carried `field(default_factory=...)` on an undecorated class, so every default
# read back as a `dataclasses.Field` object instead of a dict or a list. That
# matters here because `if bundle.solve_failures:` is the documented way to check
# for a partial result, and a Field object is truthy.
@dataclass
class ResultsBundle:
    loadcases: Dict[str, SingleResults] = field(default_factory=dict)
    loadcombinations: Dict[str, SingleResults] = field(default_factory=dict)
    # Unity-check results: one entry per check definition (see the solver's
    # `UnityCheckResult` — utilization, status colour, per-entity + governing).
    unity_check_results: List[Dict[str, Any]] = field(default_factory=list)
    # Eigenvalue results, carried as plain dicts mirroring the solver schema
    # (`ModalResults` / `BucklingResults`: {"modes": [...]}), or None when the
    # analysis was not requested.
    modal: Optional[Dict[str, Any]] = None
    buckling: Optional[Dict[str, Any]] = None
    # Single consolidated HTML report, when the solver was asked to embed it.
    report_html: Optional[str] = None
    # Free-tier provenance stamp, as a plain dict mirroring the solver's
    # `Attribution` schema (generated_by / url / engine_version / tier / text /
    # html). None on Premium, where the solver omits it entirely — so a plain
    # `if bundle.attribution:` is a reliable tier check.
    attribution: Optional[Dict[str, Any]] = None
    # Load combinations that failed to solve and are therefore MISSING from
    # `loadcombinations`. A combination with no equilibrium is an ordinary solver
    # outcome, not a defect -- the engine keeps solving the rest and records what
    # failed here -- but that makes a partial result look exactly like a complete
    # one. Always inspect before trusting an envelope, a utilization maximum or a
    # pass/fail computed over the surviving combinations:
    #
    #     if bundle.solve_failures:
    #         ...  # len(bundle.loadcombinations) is NOT what you asked for
    #
    # Note the asymmetry with load *cases*, where the same event raises straight
    # out of `calculate_to_file` and aborts the run. Collecting is the better
    # behaviour of the two, but it means the recoverable half is the quiet one.
    solve_failures: List[Dict[str, Any]] = field(default_factory=list)
    # Which engine produced these results. The input's `schema_version` says which
    # contract the caller wrote to; this says which engine answered -- the thing
    # you want in a bug report, and previously unreachable from the result object.
    engine_version: Optional[str] = None
    # Seismic (`SeismicResults`) and per-reference buckling runs (`BucklingRun`),
    # as plain dicts mirroring the solver schema. None when not requested.
    seismic: Optional[Dict[str, Any]] = None
    buckling_runs: Optional[List[Dict[str, Any]]] = None

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
        # Eigenvalue result groups (None when the analysis was not requested).
        instance.modal = _to_plain(getattr(pyd_bundle, "modal", None))
        instance.buckling = _to_plain(getattr(pyd_bundle, "buckling", None))
        instance.report_html = getattr(pyd_bundle, "report_html", None)
        instance.attribution = _to_plain(getattr(pyd_bundle, "attribution", None))
        instance.solve_failures = _to_plain(getattr(pyd_bundle, "solve_failures", []) or [])
        instance.engine_version = getattr(pyd_bundle, "engine_version", None)
        instance.seismic = _to_plain(getattr(pyd_bundle, "seismic", None))
        instance.buckling_runs = _to_plain(getattr(pyd_bundle, "buckling_runs", None))

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
                    str(k): PlateResult.from_dict(v) for k, v in (value.get("plate_results") or {}).items()
                },
                summary=ResultsSummary(**(value.get("summary") or {})) if value.get("summary") else None,
                result_type=value.get("result_type"),
                unity_checks=value.get("unity_checks"),
                errors_and_warnings=value.get("errors_and_warnings"),
                solver_diagnostics=value.get("solver_diagnostics"),
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
                    str(k): PlateResult.from_dict(v) for k, v in (value.get("plate_results") or {}).items()
                },
                summary=ResultsSummary(**(value.get("summary") or {})) if value.get("summary") else None,
                result_type=value.get("result_type"),
                unity_checks=value.get("unity_checks"),
                errors_and_warnings=value.get("errors_and_warnings"),
                solver_diagnostics=value.get("solver_diagnostics"),
            )

        instance = cls()
        instance.loadcases = lc_map
        instance.loadcombinations = comb_map
        instance.unity_check_results = list(raw.get("unity_check_results") or [])
        instance.modal = raw.get("modal")
        instance.buckling = raw.get("buckling")
        instance.report_html = raw.get("report_html")
        instance.attribution = raw.get("attribution")
        instance.solve_failures = list(raw.get("solve_failures") or [])
        instance.engine_version = raw.get("engine_version")
        instance.seismic = raw.get("seismic")
        instance.buckling_runs = raw.get("buckling_runs")
        return instance

    def to_dict(self) -> Dict[str, Any]:
        return {
            "loadcases": {k: v.to_dict() for k, v in self.loadcases.items()},
            "loadcombinations": {k: v.to_dict() for k, v in self.loadcombinations.items()},
            "unity_check_results": self.unity_check_results,
            "modal": self.modal,
            "buckling": self.buckling,
            "report_html": self.report_html,
            "attribution": self.attribution,
            "solve_failures": self.solve_failures,
            "engine_version": self.engine_version,
            "seismic": self.seismic,
            "buckling_runs": self.buckling_runs,
        }
