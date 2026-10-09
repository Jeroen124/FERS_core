"""Result requests (engine >= 0.2.68): the solver returns only what was asked for, as
dense arrays, and the SDK loads them into the usual result maps -- with anything that
was not requested reading as None, so it cannot be mistaken for a value."""

import json

import fers_calculations
import pytest
import ujson

from fers_core import (
    FERS,
    AnalysisOrder,
    Member,
    MemberSet,
    NodalLoad,
    NodalSupport,
    Node,
    ResultBlock,
    ResultRequest,
)
from fers_core.loads.enums import LimitState
from fers_core.members.enums import MemberType
from fers_core.result_requests import nodes_of
from fers_core.unity_checks import classification
from tests.common_functions import build_ipe180, build_steel_s235

pytestmark = pytest.mark.skipif(
    tuple(int(p) for p in fers_calculations.__version__.split(".")[:3]) < (0, 2, 68),
    reason="result_requests needs fers_calculations >= 0.2.68",
)

FORCES = ("fx", "fy", "fz", "mx", "my", "mz", "bw")
DISPLACEMENTS = ("dx", "dy", "dz", "rx", "ry", "rz", "warp")


def _requests():
    return [
        ResultRequest(
            ResultBlock.LOCAL_ENVELOPES,
            members=[classification("column"), classification("brace")],
            limit_state="ULS",
            components=["fx", "my", "mz"],
        ),
        ResultRequest(
            ResultBlock.LOCAL_END_FORCES,
            members=classification("beam"),
            limit_state=LimitState.ULS,
            end="start",
            components=["my", "fz"],
        ),
        ResultRequest(
            ResultBlock.LOCAL_DISPLACEMENTS,
            members=classification("beam"),
            limit_state="SLS",
            components=["dz", "ry"],
        ),
        ResultRequest(
            ResultBlock.NODE_DISPLACEMENTS,
            nodes=nodes_of(classification("column")),
            limit_state="SLS",
            components=["dx", "dy", "dz"],
        ),
        ResultRequest(ResultBlock.REACTIONS, limit_state="ULS"),
    ]


def _frame(requests=None, solve_loadcases=False) -> FERS:
    steel = build_steel_s235()
    section = build_ipe180(steel)
    model = FERS()
    fixed = NodalSupport()
    n1 = Node(0.0, 0.0, 0.0, nodal_support=fixed)
    n2 = Node(0.0, 3.0, 0.0)
    n3 = Node(4.0, 3.0, 0.0)
    n4 = Node(4.0, 0.0, 0.0, nodal_support=fixed)
    n5 = Node(4.0, 3.0, 2.0)
    n6 = Node(4.0, 0.0, 2.0, nodal_support=fixed)
    n7 = Node(4.0, 3.5, 2.0)

    def member(a, b, kind, member_type=MemberType.NORMAL):
        return Member(start_node=a, end_node=b, section=section, classification=kind, member_type=member_type)

    model.add_member_set(
        MemberSet(
            members=[
                member(n1, n2, "column"),
                member(n2, n3, "beam"),
                member(n3, n4, "column"),
                member(n3, n5, "beam"),
                member(n5, n6, "column"),
                member(n1, n3, "brace", MemberType.TRUSS),
                member(n5, n7, "link", MemberType.RIGID),
            ]
        )
    )
    wind = model.create_load_case(name="Wind")
    snow = model.create_load_case(name="Snow")
    NodalLoad(node=n2, load_case=wind, magnitude=5000.0, direction=(1.0, 0.0, 0.0))
    NodalLoad(node=n7, load_case=snow, magnitude=-8000.0, direction=(0.0, 1.0, 0.0))
    uls = model.create_load_combination("ULS1", {wind: 1.5, snow: 1.35}, situation="ULS1", check="ALL")
    uls.limit_state = LimitState.ULS
    sls = model.create_load_combination("SLS1", {wind: 1.0, snow: 1.0}, situation="SLS1", check="ALL")
    sls.limit_state = LimitState.SLS
    options = model.settings.analysis_options
    options.order = AnalysisOrder.LINEAR
    options.solve_loadcases = solve_loadcases
    options.result_requests = requests
    return model


@pytest.fixture(scope="module")
def solved(tmp_path_factory):
    folder = tmp_path_factory.mktemp("requests")
    full, selected = folder / "full.json", folder / "selected.json"
    _frame().run_analysis_to_file(str(full))
    _frame(_requests()).run_analysis_to_file(str(selected))
    return full, selected


def _values(obj, names):
    return {name: getattr(obj, name) for name in names}


def test_requested_values_load_into_the_usual_maps(solved):
    full_path, selected_path = solved
    full = FERS.from_json(str(full_path)).resultsbundle.loadcombinations
    selected = FERS.from_json(str(selected_path)).resultsbundle.loadcombinations
    uls, sls = selected["ULS1"], selected["SLS1"]

    # Columns and the brace: envelopes, three components; nothing else.
    for mid in ("1", "3", "5", "6"):
        got, ref = uls.member_results[mid], full["ULS1"].member_results[mid]
        for block in ("local_maximums", "local_minimums"):
            for c in FORCES:
                expected = getattr(getattr(ref, block), c) if c in ("fx", "my", "mz") else None
                assert getattr(getattr(got, block), c) == expected, (mid, block, c)
        assert set(_values(got.local_start_forces, FORCES).values()) == {None}
    # Beams: the start-end forces asked for, and not the other end.
    for mid in ("2", "4"):
        got, ref = uls.member_results[mid], full["ULS1"].member_results[mid]
        assert got.local_start_forces.my == ref.local_start_forces.my
        assert got.local_start_forces.fz == ref.local_start_forces.fz
        assert got.local_start_forces.fx is None and got.local_end_forces.my is None
        assert got.local_maximums.fx is None
        sls_got, sls_ref = sls.member_results[mid], full["SLS1"].member_results[mid]
        for block in ("local_displacement_start_node", "local_displacement_end_node"):
            assert getattr(sls_got, block).dz == getattr(sls_ref, block).dz
            assert getattr(sls_got, block).ry == getattr(sls_ref, block).ry
            assert getattr(sls_got, block).dx is None
    # The rigid link has no results, and nothing was asked of it.
    assert list(uls.member_results) == ["1", "2", "3", "4", "5", "6"]
    assert list(sls.member_results) == ["2", "4"]

    # Node displacements: the column nodes, three components, SLS only.
    assert list(sls.displacement_nodes) == ["1", "2", "3", "4", "5", "6"]
    for nid in sls.displacement_nodes:
        got, ref = sls.displacement_nodes[nid], full["SLS1"].displacement_nodes[nid]
        assert _values(got, ("dx", "dy", "dz")) == _values(ref, ("dx", "dy", "dz"))
        assert got.rz is None
    assert len(uls.displacement_nodes) == 0

    # Reactions: every component of the supported nodes; where and which support
    # are not part of a selection.
    assert set(uls.reaction_nodes) == set(full["ULS1"].reaction_nodes)
    for nid, reaction in uls.reaction_nodes.items():
        assert _values(reaction.nodal_forces, FORCES) == _values(
            full["ULS1"].reaction_nodes[nid].nodal_forces, FORCES
        )
        assert reaction.location.X is None and reaction.support_id is None


def test_the_arrays_are_kept_as_well(solved):
    bundle = FERS.from_json(str(solved[1])).resultsbundle
    assert [s["block"] for s in bundle.selections] == [r.to_dict()["block"] for r in _requests()]
    envelopes = bundle.selections[0]
    assert envelopes["group"] == "loadcombinations" and envelopes["result_sets"] == ["ULS1"]
    assert envelopes["values"].shape == (1, 4, 2, 3)
    assert not envelopes["values"].flags.writeable
    member = bundle.loadcombinations["ULS1"].member_results[str(envelopes["ids"][0])]
    assert envelopes["values"][0, 0, 1, 1] == member.local_minimums.my


def test_a_selected_result_round_trips(solved, tmp_path):
    model = FERS.from_json(str(solved[1]))
    data = model.to_dict()
    for single in data["results"]["loadcombinations"].values():
        assert single["member_results"] == {} and single["displacement_nodes"] == {}
        assert single["reaction_nodes"] == {}
    assert [s["request"] for s in data["results"]["selections"]] == [0, 1, 2, 3, 4]
    expected = ujson.dumps(model.resultsbundle.to_dict())
    again = FERS.from_dict(json.loads(ujson.dumps(data)))
    assert ujson.dumps(again.resultsbundle.to_dict()) == expected
    path = tmp_path / "saved.json"
    model.save_to_json(str(path))
    assert ujson.dumps(FERS.from_json(str(path)).resultsbundle.to_dict()) == expected


def test_requests_round_trip_through_the_options():
    model = _frame(_requests())
    model.validate_schema()
    wire = model.to_dict(include_results=False)["analysis"]["options"]["result_requests"]
    assert wire[1] == {
        "block": "local_end_forces",
        "members": [{"type": "MemberClassification", "value": "beam"}],
        "limit_state": "ULS",
        "components": ["my", "fz"],
        "end": "start",
    }
    rebuilt = FERS.from_dict(model.to_dict(include_results=False))
    assert rebuilt.settings.analysis_options.result_requests == _requests()


def test_a_request_that_cannot_be_met_is_refused_before_the_solve(tmp_path):
    model = _frame([ResultRequest(ResultBlock.LOCAL_ENVELOPES, components=["dx"])])
    with pytest.raises(RuntimeError, match="has no component Dx"):
        model.run_analysis_to_file(str(tmp_path / "never.json"))


def test_an_unnarrowed_request_covers_the_load_cases():
    model = _frame([ResultRequest(ResultBlock.NODE_DISPLACEMENTS, components=["dy"])], solve_loadcases=True)
    model.run_analysis()
    reference = _frame(solve_loadcases=True)
    reference.run_analysis()
    for group in ("loadcases", "loadcombinations"):
        for name, single in getattr(model.resultsbundle, group).items():
            ref = getattr(reference.resultsbundle, group)[name]
            assert single.displacement_nodes["2"].dy == ref.displacement_nodes["2"].dy
            assert single.displacement_nodes["2"].dx is None
