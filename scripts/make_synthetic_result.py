"""Write a solver result file without solving, for measuring how results load.

What a result costs to load depends on its shape and size, not on whether the
numbers solve anything, so a generated file can stand in for a model that cannot
be shared. The model section is built through the SDK, so ``FERS.from_json``
rebuilds it like a real one. The results section follows the engine's
``calculate_to_file`` layout: compact JSON, ``results`` as the last key, every map
keyed by quoted integer ids in numeric order, combinations in byte order.

The defaults reproduce the file of an integrator's report: 2652 nodes, 3090
members, 25 load combinations, ``solve_loadcases=False`` and the five-token
``result_filter``, about 81.5 MB::

    python scripts/make_synthetic_result.py out.json
    python scripts/make_synthetic_result.py big.json --nodes 7147 --members 8546 \\
        --combinations 31 --loadcases 15
"""

from __future__ import annotations

import argparse
import json
import math
import random
from typing import Any, Dict, List

FILTER_TOKENS = [
    "local_envelopes",
    "local_end_forces",
    "local_displacements",
    "node_displacements",
    "reactions",
]
_FORCES = ("fx", "fy", "fz", "mx", "my", "mz")
_DISPLACEMENTS = ("dx", "dy", "dz", "rx", "ry", "rz")
_COMPACT = (",", ":")


def _build_model(nodes: int, members: int, loadcases: int, combinations: int, filtered: bool, solve_lc: bool):
    from fers_core import FERS, Material, Member, MemberSet, NodalLoad, NodalSupport, Node, Section

    model = FERS()
    width = math.ceil(math.sqrt(nodes))
    grid = [Node(float(i % width), float(i // width), 0.0) for i in range(nodes)]
    support = NodalSupport()
    for node in grid[:width]:
        node.nodal_support = support

    # A chain through every node first: the model only serializes nodes that a member
    # uses, and the engine reports displacements for exactly those.
    edges = [(i, i + 1) for i in range(nodes - 1)]
    edges += [(i, i + width) for i in range(nodes - width)]
    if len(edges) < members:
        raise SystemExit(f"{nodes} nodes give at most {len(edges)} members; ask for more nodes")

    steel = Material(name="Steel", e_mod=210e9, g_mod=80.769e9, density=7850, yield_stress=235e6)
    section = Section(name="Synthetic", material=steel, i_y=1.01e-6, i_z=13.21e-6, j=0.027e-6, area=0.00196)
    model.add_member_set(
        MemberSet(
            members=[
                Member(start_node=grid[a], end_node=grid[b], section=section) for a, b in edges[:members]
            ]
        )
    )

    cases = [model.create_load_case(name=f"LC{i + 1}") for i in range(max(loadcases, 2))]
    for i, case in enumerate(cases):
        NodalLoad(node=grid[-1 - i], load_case=case, magnitude=-1000.0, direction=(0.0, 1.0, 0.0))
    for i in range(combinations):
        model.create_load_combination(
            name=f"ULS{i + 1}",
            load_cases_factors={case: 1.0 + 0.1 * j for j, case in enumerate(cases)},
            situation="ULS",
            check="ALL",
        )

    options = model.settings.analysis_options
    options.solve_loadcases = solve_lc
    options.result_filter = list(FILTER_TOKENS) if filtered else None
    return model, grid, support, [lc.name for lc in cases], [c.name for c in model.load_combinations]


class _Values:
    """Numbers with the spread of significant digits the engine writes."""

    def __init__(self, seed: int, digits: tuple):
        self._rng = random.Random(seed)
        self._digits = digits

    def __call__(self, scale: float) -> float:
        value = self._rng.uniform(-scale, scale)
        return float(f"{value:.{self._rng.randint(*self._digits)}g}")

    def zero(self) -> float:
        # Warping is off in the stand-in, and the engine writes both signs of zero.
        return -0.0 if self._rng.random() < 0.5 else 0.0


def _forces(v: _Values, scale: float) -> Dict[str, float]:
    block = {c: v(scale) for c in _FORCES}
    block["bw"] = v.zero()
    return block


def _displacement(v: _Values) -> Dict[str, float]:
    block = {c: v(1e-2 if c[0] == "d" else 1e-3) for c in _DISPLACEMENTS}
    block["warp"] = v.zero()
    return block


def _member_entry(v: _Values, filtered: bool) -> Dict[str, Any]:
    entry: Dict[str, Any] = {}
    if not filtered:
        for block in ("start_node_forces", "end_node_forces", "maximums", "minimums"):
            entry[block] = _forces(v, 1e5)
    for block in ("local_start_forces", "local_end_forces", "local_maximums", "local_minimums"):
        entry[block] = _forces(v, 1e5)
    entry["local_displacement_start_node"] = _displacement(v)
    entry["local_displacement_end_node"] = _displacement(v)
    if filtered:
        entry["section_forces"] = []
        entry["internal_force_series"] = []
    else:
        stations = [{"x_frac": x, "forces": _forces(v, 1e5)} for x in (0.25, 0.5, 0.75)]
        entry["section_forces"] = stations
        entry["internal_force_series"] = (
            [{"x_frac": 0.0, "forces": _forces(v, 1e5)}]
            + stations
            + [{"x_frac": 1.0, "forces": _forces(v, 1e5)}]
        )
    return entry


def _single_result(name, kind, rid, grid, member_ids, support, v, filtered) -> Dict[str, Any]:
    supported = [n for n in grid if n.nodal_support is not None]
    return {
        "name": name,
        "result_type": {kind: rid},
        "displacement_nodes": {str(n.id): _displacement(v) for n in grid},
        "reaction_nodes": {
            str(n.id): {
                "nodal_forces": _forces(v, 1e5),
                "location": {"X": n.X, "Y": n.Y, "Z": n.Z},
                "support_id": support.id,
            }
            for n in supported
        },
        "member_results": {str(m): _member_entry(v, filtered) for m in member_ids},
        "plate_results": {},
        "summary": {
            "total_displacements": len(grid),
            "total_member_forces": len(member_ids),
            "total_reaction_forces": 1,
            "total_plate_forces": 0,
        },
        "errors_and_warnings": {"errors": [], "warnings": []},
        "solver_diagnostics": {
            "iterations": 6,
            "solve_time_ms": v(100.0) + 100.0,
            "converged": True,
            "residual_norm": abs(v(1e-7)),
            "analysis_method": "P_DELTA",
        },
    }


def write_synthetic_result(
    path: str,
    *,
    nodes: int = 2652,
    members: int = 3090,
    combinations: int = 25,
    loadcases: int = 0,
    filtered: bool = True,
    seed: int = 1,
    digits: tuple = (6, 13),
) -> int:
    """Write the file and return its size in bytes. ``loadcases`` > 0 also solves them."""
    model, grid, support, case_names, comb_names = _build_model(
        nodes, members, loadcases, combinations, filtered, solve_lc=loadcases > 0
    )
    member_ids = sorted(m.id for m in model.get_all_members())
    head = model.to_dict(include_results=False)
    head.pop("results", None)
    v = _Values(seed, digits)

    def result_map(names: List[str], kind: str) -> str:
        parts = []
        for rid, name in sorted(enumerate(names, start=1), key=lambda item: item[1]):
            body = _single_result(name, kind, rid, grid, member_ids, support, v, filtered)
            parts.append(json.dumps(name) + ":" + json.dumps(body, separators=_COMPACT))
        return "{" + ",".join(parts) + "}"

    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(json.dumps(head, separators=_COMPACT)[:-1])
        f.write(',"results":{"engine_version":"0.2.66","loadcases":')
        f.write(result_map(case_names[:loadcases], "Loadcase") if loadcases else "{}")
        f.write(',"loadcombinations":')
        f.write(result_map(comb_names, "Loadcombination"))
        f.write(',"solve_failures":[],"unity_check_results":[]}}')
        return f.tell()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("path")
    parser.add_argument("--nodes", type=int, default=2652)
    parser.add_argument("--members", type=int, default=3090)
    parser.add_argument("--combinations", type=int, default=25)
    parser.add_argument("--loadcases", type=int, default=0, help="load cases solved into the result")
    parser.add_argument("--unfiltered", action="store_true", help="the engine's default full output")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument(
        "--digits", type=int, nargs=2, default=(6, 13), help="range of significant digits per number"
    )
    args = parser.parse_args()
    size = write_synthetic_result(
        args.path,
        nodes=args.nodes,
        members=args.members,
        combinations=args.combinations,
        loadcases=args.loadcases,
        filtered=not args.unfiltered,
        seed=args.seed,
        digits=tuple(args.digits),
    )
    print(f"{args.path}: {size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
