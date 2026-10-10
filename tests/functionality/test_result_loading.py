"""Loading results: the compact, streamed loader must give exactly what the old one gave.

Up to 0.1.97 a result was parsed whole, validated into the generated pydantic models
and copied into one object per value. ``_legacy`` below is that path, frozen: every
test that compares against it holds the new loader to the same numbers, the same
zero-filled blocks and the same ``to_dict()`` text, key order included.
"""

import copy
import json
import locale
import pickle

import pytest
import ujson

from fers_core import FERS, AnalysisOrder, Member, MemberSet, NodalLoad, NodalSupport, Node, check_beam
from fers_core.members.enums import MemberType
from fers_core.results._loader import results_from_engine_output
from fers_core.results.compact import (
    DISPLACEMENT_COMPONENTS,
    FORCE_BLOCKS,
    FORCE_COMPONENTS,
    MemberResultTable,
    NodeDisplacementTable,
)
from fers_core.results.member import MemberResult
from fers_core.results.nodes import NodeForces, NodeLocation, ReactionNodeResult, SectionForce
from fers_core.results.plate import PlateResult
from fers_core.results.resultsbundle import ResultsBundle
from fers_core.results.singleresults import jsonable
from fers_core.types.pydantic_models import ResultsBundle as ResultsBundleSchema
from tests.common_functions import build_ipe180, build_steel_s235
from tests.functionality.test_plate_results import build_plate_strip_pressure_model

_FILTER = ["local_envelopes", "local_end_forces", "local_displacements", "node_displacements", "reactions"]


def _frame(**options) -> FERS:
    """A small 3D frame with a truss brace and a rigid link, two load cases, two combinations."""
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
    members = [
        Member(start_node=n1, end_node=n2, section=section),
        Member(start_node=n2, end_node=n3, section=section),
        Member(start_node=n3, end_node=n4, section=section),
        Member(start_node=n3, end_node=n5, section=section),
        Member(start_node=n5, end_node=n6, section=section),
        Member(start_node=n1, end_node=n3, section=section, member_type=MemberType.TRUSS),
        Member(start_node=n5, end_node=n7, section=section, member_type=MemberType.RIGID),
    ]
    model.add_member_set(MemberSet(members=members))
    wind = model.create_load_case(name="Wind")
    snow = model.create_load_case(name="Snow")
    NodalLoad(node=n2, load_case=wind, magnitude=5000.0, direction=(1.0, 0.0, 0.0))
    NodalLoad(node=n7, load_case=snow, magnitude=-8000.0, direction=(0.0, 1.0, 0.0))
    model.create_load_combination(
        name="ULS1", load_cases_factors={wind: 1.5, snow: 1.35}, situation="ULS", check="ALL"
    )
    model.create_load_combination(
        name="SLS1", load_cases_factors={wind: 1.0, snow: 1.0}, situation="SLS", check="ALL"
    )
    opts = model.settings.analysis_options
    opts.order = options.pop("order", AnalysisOrder.LINEAR)
    for name, value in options.items():
        setattr(opts, name, value)
    return model


def _check_beam() -> FERS:
    return check_beam(6.0, "IPE300", material="S235", support="simply_supported", udl=10000.0)


def _plates() -> FERS:
    return build_plate_strip_pressure_model()[0]


_VARIANTS = {
    "unfiltered": lambda: _frame(),
    "filtered": lambda: _frame(result_filter=list(_FILTER), solve_loadcases=False),
    "deflected_shape": lambda: _frame(include_member_deflected_shape=True),
    "second_order": lambda: _frame(order=AnalysisOrder.NONLINEAR),
    "plates": _plates,
    "unity_checks": _check_beam,
}


@pytest.fixture(scope="module")
def solved(tmp_path_factory):
    """Each variant solved once, through the engine, to a file."""
    paths = {}
    for name, build in _VARIANTS.items():
        path = tmp_path_factory.mktemp("results") / f"{name}.json"
        build().run_analysis_to_file(str(path))
        paths[name] = path
    return paths


# --- the frozen 0.1.97 loader -----------------------------------------------


def _forces(f):
    return {c: float(getattr(f, c, 0.0)) for c in FORCE_COMPONENTS}


def _displacement(d):
    return {c: float(getattr(d, c, 0.0)) for c in DISPLACEMENT_COMPONENTS}


def _section(s):
    return {"x_frac": float(s.x_frac), "forces": _forces(s.forces)}


def _sample(s):
    return {"x_frac": float(s.x_frac), "displacement": [float(v) for v in s.displacement.root]}


def _member(r):
    out = {name: _forces(getattr(r, name)) for name in FORCE_BLOCKS}
    out["local_displacement_start_node"] = _displacement(r.local_displacement_start_node)
    out["local_displacement_end_node"] = _displacement(r.local_displacement_end_node)
    out["section_forces"] = [_section(s) for s in r.section_forces or []]
    out["member_displacements"] = [_sample(s) for s in r.member_displacements or []]
    out["internal_force_series"] = (
        None if r.internal_force_series is None else [_section(s) for s in r.internal_force_series]
    )
    peak = r.member_displacement_peak
    out["member_displacement_peak"] = None if peak is None else _sample(peak)
    return out


def _plate(p):
    return PlateResult.from_pydantic(p).to_dict()


def _summary(s):
    if not s:
        return None
    names = ("total_displacements", "total_member_forces", "total_reaction_forces", "total_plate_forces")
    return {name: getattr(s, name) for name in names}


def _single(r):
    return {
        "name": r.name or "",
        "displacement_nodes": {str(k): _displacement(v) for k, v in (r.displacement_nodes or {}).items()},
        "reaction_nodes": {
            str(k): {
                "location": {"X": float(v.location.X), "Y": float(v.location.Y), "Z": float(v.location.Z)},
                "nodal_forces": _forces(v.nodal_forces),
                "support_id": int(v.support_id or 0),
            }
            for k, v in (r.reaction_nodes or {}).items()
        },
        "member_results": {str(k): _member(v) for k, v in (r.member_results or {}).items()},
        "plate_results": {str(k): _plate(v) for k, v in (r.plate_results or {}).items()},
        "summary": _summary(r.summary),
        "result_type": r.result_type.model_dump() if r.result_type is not None else None,
        "unity_checks": None,
        "errors_and_warnings": jsonable(r.errors_and_warnings.model_dump())
        if r.errors_and_warnings
        else None,
        "solver_diagnostics": jsonable(r.solver_diagnostics.model_dump()) if r.solver_diagnostics else None,
    }


def _dump(value):
    return None if value is None else jsonable(value.model_dump() if hasattr(value, "model_dump") else value)


def _legacy(text: str) -> dict:
    pyd = ResultsBundleSchema(**json.loads(text)["results"])
    return {
        "loadcases": {str(k): _single(v) for k, v in pyd.loadcases.items()},
        "loadcombinations": {str(k): _single(v) for k, v in pyd.loadcombinations.items()},
        "unity_check_results": [_dump(u) for u in pyd.unity_check_results or []],
        "modal": _dump(pyd.modal),
        "buckling": _dump(pyd.buckling),
        "report_html": pyd.report_html,
        "attribution": _dump(pyd.attribution),
        "solve_failures": [_dump(f) for f in pyd.solve_failures or []],
        "engine_version": pyd.engine_version,
        "seismic": _dump(pyd.seismic),
        "buckling_runs": None if pyd.buckling_runs is None else [_dump(b) for b in pyd.buckling_runs],
    }


def _text(path):
    return path.read_text(encoding="utf-8")


# --- parity -----------------------------------------------------------------


@pytest.mark.parametrize("variant", list(_VARIANTS))
def test_loading_matches_the_old_loader(solved, variant):
    path = solved[variant]
    loaded = FERS.from_json(str(path))
    # ujson text, not ==: -0.0 == 0.0, and a lost sign is a changed result.
    assert ujson.dumps(loaded.resultsbundle.to_dict()) == ujson.dumps(_legacy(_text(path)))


@pytest.mark.parametrize("variant", ["unfiltered", "deflected_shape", "unity_checks"])
def test_every_entry_point_loads_the_same_result(solved, variant):
    text = _text(solved[variant])
    expected = ujson.dumps(FERS.from_json(str(solved[variant])).resultsbundle.to_dict())
    assert ujson.dumps(FERS.from_dict(json.loads(text)).resultsbundle.to_dict()) == expected
    assert ujson.dumps(results_from_engine_output(text).to_dict()) == expected
    pyd = ResultsBundleSchema(**json.loads(text)["results"])
    assert ujson.dumps(ResultsBundle.from_pydantic(pyd).to_dict()) == expected


def test_run_analysis_loads_through_the_same_path():
    model = _frame(include_member_deflected_shape=True)
    model.run_analysis()
    member = model.resultsbundle.loadcombinations["ULS1"].member_results["2"]
    assert member.member_displacements and member.member_displacement_peak is not None
    assert model.resultsbundle.loadcases["Wind"].displacement_nodes["2"].dx > 0.0


def test_reordered_keys_load_the_same(solved, tmp_path):
    def reverse(value):
        if isinstance(value, dict):
            return {k: reverse(v) for k, v in reversed(list(value.items()))}
        if isinstance(value, list):
            return [reverse(v) for v in value]
        return value

    path = solved["deflected_shape"]
    shuffled = tmp_path / "reversed.json"
    shuffled.write_text(json.dumps(reverse(json.loads(_text(path))), indent=2), encoding="utf-8")
    original = FERS.from_json(str(path)).resultsbundle
    reloaded = FERS.from_json(str(shuffled)).resultsbundle
    for group in ("loadcases", "loadcombinations"):
        for name in getattr(original, group):
            before = getattr(original, group)[name].to_dict()
            after = getattr(reloaded, group)[name].to_dict()
            # Maps come back in the reversed order; their contents must not change.
            assert {k: ujson.dumps(v, sort_keys=True) for k, v in before["member_results"].items()} == {
                k: ujson.dumps(v, sort_keys=True) for k, v in after["member_results"].items()
            }
            assert ujson.dumps(before["displacement_nodes"], sort_keys=True) == ujson.dumps(
                after["displacement_nodes"], sort_keys=True
            )


def test_the_model_section_loads_as_before(solved):
    path = solved["filtered"]
    data = json.loads(_text(path))
    assert FERS.from_json(str(path)).to_dict(include_results=False) == FERS.from_dict(data).to_dict(
        include_results=False
    )


# --- the tables -------------------------------------------------------------


@pytest.fixture(scope="module")
def filtered(solved):
    return FERS.from_json(str(solved["filtered"])).resultsbundle.loadcombinations["ULS1"]


def test_tables_behave_like_the_dicts_they_replace(solved, filtered):
    members = filtered.member_results
    raw = json.loads(_text(solved["filtered"]))["results"]["loadcombinations"]["ULS1"]
    assert isinstance(members, MemberResultTable)
    assert list(members) == list(raw["member_results"])
    assert len(members) == len(raw["member_results"])
    assert list(reversed(members)) == list(reversed(list(raw["member_results"])))
    assert "1" in members and "999" not in members and 1 not in members
    assert members.get("999") is None
    with pytest.raises(KeyError):
        members["999"]
    assert next(iter(members.values())).local_maximums.fx == members[next(iter(members))].local_maximums.fx
    assert repr(members) == f"<MemberResultTable: {len(members)} members>"
    nodes = filtered.displacement_nodes
    assert isinstance(nodes, NodeDisplacementTable)
    assert list(nodes) == list(raw["displacement_nodes"])
    assert {k: v.dy for k, v in nodes.items()} == {k: v["dy"] for k, v in raw["displacement_nodes"].items()}


def test_membership_does_not_build_a_result(filtered, monkeypatch):
    def refuse(*_args):
        raise AssertionError("built a MemberResult just to test membership")

    monkeypatch.setattr(MemberResultTable, "_build", refuse)
    assert "1" in filtered.member_results


def test_values_are_plain_floats_and_filtered_blocks_read_as_zero(filtered):
    member = filtered.member_results["1"]
    assert type(member.local_maximums.my) is float
    assert type(filtered.displacement_nodes["2"].dx) is float
    # The filter removed the global blocks; as before, they read as zeros.
    assert all(getattr(member.start_node_forces, c) == 0.0 for c in FORCE_COMPONENTS)
    assert member.section_forces == () and member.internal_force_series == ()


def test_the_rigid_link_has_no_entry_and_the_truss_has_no_section_forces(solved):
    single = FERS.from_json(str(solved["unfiltered"])).resultsbundle.loadcombinations["ULS1"]
    assert "7" not in single.member_results  # rigid
    assert single.member_results["6"].section_forces == ()  # truss
    assert len(single.member_results["2"].section_forces) == 3  # beam, interior stations


# --- read-only --------------------------------------------------------------


def test_loaded_results_are_read_only(solved):
    single = FERS.from_json(str(solved["deflected_shape"])).resultsbundle.loadcombinations["ULS1"]
    member = single.member_results["2"]
    with pytest.raises(AttributeError, match=r"read-only.*\.copy\(\)"):
        member.local_maximums = NodeForces()
    with pytest.raises(AttributeError, match="read-only"):
        member.local_maximums.my = 0.0
    with pytest.raises(AttributeError, match="read-only"):
        del member.section_forces
    with pytest.raises(AttributeError, match="read-only"):
        member.section_forces[0].x_frac = 0.5
    with pytest.raises(AttributeError, match="read-only"):
        single.displacement_nodes["2"].dy = 0.0
    with pytest.raises(AttributeError):
        member.member_displacements.append((0.5, (0.0, 0.0, 0.0)))
    assert isinstance(member, MemberResult) and isinstance(member.local_maximums, NodeForces)
    assert isinstance(member.section_forces[0], SectionForce)


def test_copy_gives_back_editable_objects(solved):
    single = FERS.from_json(str(solved["deflected_shape"])).resultsbundle.loadcombinations["ULS1"]
    members = single.member_results.copy()
    assert type(members) is dict and type(members["2"]) is MemberResult
    assert type(members["2"].local_maximums) is NodeForces and type(members["2"].section_forces) is list
    members["2"].local_maximums.my = 1.0
    assert members["2"].local_maximums.my == 1.0
    assert ujson.dumps({k: v.to_dict() for k, v in members.items() if k != "2"}) == ujson.dumps(
        {k: v.to_dict() for k, v in single.member_results.items() if k != "2"}
    )
    nodes = single.displacement_nodes.copy()
    nodes["2"].dy = 0.0
    assert nodes["2"].dy == 0.0


def test_results_survive_pickle_and_copy(solved):
    bundle = FERS.from_json(str(solved["deflected_shape"])).resultsbundle
    expected = ujson.dumps(bundle.to_dict())
    assert ujson.dumps(pickle.loads(pickle.dumps(bundle)).to_dict()) == expected
    assert ujson.dumps(copy.deepcopy(bundle).to_dict()) == expected
    member = bundle.loadcombinations["ULS1"].member_results["2"]
    assert copy.copy(member).to_dict() == member.to_dict()
    assert pickle.loads(pickle.dumps(member)).to_dict() == member.to_dict()


def test_renderers_run_on_loaded_results(solved):
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg")
    model = FERS.from_json(str(solved["deflected_shape"]))
    model.plot_results_2d(plane="xy", loadcombination="ULS1", plot_local_bending_moment="M_z")
    member_model = next(m for m in model.get_all_members() if m.id == 2)
    member = model.resultsbundle.loadcombinations["ULS1"].member_results["2"]
    member.plot_diagram(member_model, "My")
    assert member.render_diagram(member_model, "Mz")
    zeros = [0.0, 0.0, 0.0]
    assert member.render_deformed_shape(member_model, zeros, zeros, zeros, zeros)


# --- errors and edge cases --------------------------------------------------


def test_validation_errors_read_as_before(solved, tmp_path):
    data = json.loads(_text(solved["unfiltered"]))
    data["results"]["loadcombinations"]["ULS1"]["member_results"]["3"]["local_maximums"]["fx"] = "abc"
    broken = tmp_path / "broken.json"
    broken.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(Exception) as before:
        ResultsBundleSchema(**data["results"])
    with pytest.raises(Exception) as now:
        FERS.from_json(str(broken))
    assert str(now.value) == str(before.value)


def test_missing_required_results_fields_still_fail(solved):
    data = json.loads(_text(solved["unfiltered"]))
    del data["results"]["loadcases"]
    with pytest.raises(Exception, match="loadcases"):
        FERS.from_dict(data)


@pytest.mark.parametrize("results", [None, {}])
def test_empty_results_mean_no_results(solved, tmp_path, results):
    data = json.loads(_text(solved["unfiltered"]))
    data["results"] = results
    path = tmp_path / "empty.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    assert FERS.from_json(str(path)).resultsbundle is None
    assert FERS.from_dict(data).resultsbundle is None


def test_the_legacy_resultsbundle_key_still_loads(solved, tmp_path):
    data = json.loads(_text(solved["unfiltered"]))
    data["resultsbundle"] = data.pop("results")
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    assert FERS.from_json(str(path)).resultsbundle.loadcombinations["ULS1"].member_results["1"]


def test_engine_output_without_results_is_refused():
    with pytest.raises(ValueError, match="No 'results' field"):
        results_from_engine_output('{"model": {}, "results": null}')
    with pytest.raises(Exception, match="loadcases"):
        results_from_engine_output('{"model": {}, "results": {}}')


def test_null_bw_and_warp_read_as_zero(solved, tmp_path):
    data = json.loads(_text(solved["unfiltered"]))
    single = data["results"]["loadcombinations"]["ULS1"]
    single["member_results"]["1"]["local_maximums"]["bw"] = None
    single["displacement_nodes"]["2"]["warp"] = None
    path = tmp_path / "nulls.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    loaded = FERS.from_json(str(path)).resultsbundle.loadcombinations["ULS1"]
    assert loaded.member_results["1"].local_maximums.bw == 0.0
    assert loaded.displacement_nodes["2"].warp == 0.0


def test_non_ascii_names_in_a_utf8_file_with_a_bom(tmp_path):
    model = _frame()
    model.load_combinations[0].name = "ULS Á — \U0001f600"
    path = tmp_path / "names.json"
    model.run_analysis_to_file(str(path))
    path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes())
    loaded = FERS.from_json(str(path)).resultsbundle
    assert "ULS Á — \U0001f600" in loaded.loadcombinations


@pytest.mark.skipif(
    locale.getpreferredencoding(False).lower().replace("-", "") == "utf8",
    reason="needs a platform codec other than UTF-8",
)
def test_a_file_in_the_platform_codec_still_loads(solved, tmp_path):
    data = json.loads(_text(solved["unfiltered"]))
    data["results"]["loadcombinations"]["ULS1"]["name"] = "ULS café"
    path = tmp_path / "legacy_codec.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding=locale.getpreferredencoding(False))
    assert FERS.from_json(str(path)).resultsbundle.loadcombinations["ULS1"].name == "ULS café"


# --- the bugs fixed with this ------------------------------------------------


def test_from_raw_dict_reads_real_results(solved):
    for variant in ("unfiltered", "deflected_shape", "plates"):
        raw = json.loads(_text(solved[variant]))["results"]
        loaded = FERS.from_json(str(solved[variant])).resultsbundle
        rebuilt = ResultsBundle.from_raw_dict(raw)
        for group in ("loadcases", "loadcombinations"):
            for name, single in getattr(loaded, group).items():
                for part in ("member_results", "displacement_nodes", "reaction_nodes", "plate_results"):
                    assert ujson.dumps(getattr(rebuilt, group)[name].to_dict()[part]) == ujson.dumps(
                        single.to_dict()[part]
                    ), (variant, group, name, part)


def test_to_dict_survives_json_with_unity_check_results():
    beam = _check_beam()
    beam.run_analysis()
    status = beam.resultsbundle.unity_check_results[0]["status"]
    assert not isinstance(status, str)  # in memory: the enum, as before
    assert (
        ujson.loads(ujson.dumps(beam.to_dict()))["results"]["unity_check_results"][0]["status"]
        == status.value
    )


def test_a_second_run_analysis_sends_no_results(monkeypatch):
    import fers_calculations

    beam = _check_beam()
    beam.run_analysis()
    sent = []
    original = fers_calculations.calculate_from_json

    def capture(input_json, **kwargs):
        sent.append(json.loads(input_json))
        return original(input_json, **kwargs)

    monkeypatch.setattr(fers_calculations, "calculate_from_json", capture)
    beam.run_analysis()
    assert sent[0]["results"] is None
    assert beam.resultsbundle.unity_check_results


def test_save_to_json_works_with_its_default_arguments(solved, tmp_path):
    model = FERS.from_json(str(solved["unity_checks"]))
    path = tmp_path / "saved.json"
    model.save_to_json(str(path))
    assert ujson.dumps(FERS.from_json(str(path)).resultsbundle.to_dict()) == ujson.dumps(
        model.resultsbundle.to_dict()
    )


def test_result_classes_have_real_defaults():
    reaction = ReactionNodeResult()
    assert isinstance(reaction.location, NodeLocation) and isinstance(reaction.nodal_forces, NodeForces)
    plate = PlateResult()
    assert isinstance(plate.centroid, NodeLocation) and plate.nodal_forces_global == {}
