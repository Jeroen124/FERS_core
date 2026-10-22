"""Self-weight must reach the load combinations: the case that takes it, and the
refusal of a model whose combinations all leave it out."""

import pytest

from fers_core.builders import create_beam
from fers_core.settings.self_weight import self_weight_outside_combinations

SPAN = 6.0
IMPOSED = 5_000.0  # N/m
CODE = "self_weight_not_in_combinations"


def _beam():
    """A 6 m IPE300 with load case Q (id 1) holding 5 kN/m."""
    return create_beam(SPAN, "IPE300", udl=IMPOSED, load_case_name="Q")


def _bare(model):
    """Self-weight on, no case for it, and a ULS combination of Q alone."""
    model.settings.analysis_options.enable_self_weight = True
    model.create_load_combination("ULS", {model.load_cases[0]: 1.5}, limit_state="ULS")
    return model


def _beam_weight(model):
    section = model.members[0].section
    return section.material.density * section.area * 9.81 * SPAN


def _vertical_reaction(results):
    return sum(r.nodal_forces.fy for r in results.reaction_nodes.values())


def test_create_load_case_with_self_weight_sets_both_options():
    model = _beam()
    dead = model.create_load_case("G", self_weight=True)
    options = model.settings.analysis_options
    assert options.enable_self_weight is True
    assert options.self_weight_load_case_id == dead.id
    assert model.analysis.create_load_case("Wind").id != dead.id


def test_self_weight_in_g_reaches_the_combination():
    model = _beam()
    dead = model.create_load_case("G", self_weight=True)
    model.create_load_combination("ULS", {dead: 1.35, model.load_cases[0]: 1.5}, limit_state="ULS")
    model.run_analysis()
    uls = model.resultsbundle.loadcombinations["ULS"]
    expected = 1.35 * _beam_weight(model) + 1.5 * IMPOSED * SPAN
    assert _vertical_reaction(uls) == pytest.approx(expected, rel=1e-6)
    assert not (uls.errors_and_warnings or {}).get("warnings")


def test_only_one_case_takes_the_self_weight():
    model = _beam()
    model.create_load_case("G", self_weight=True)
    with pytest.raises(ValueError, match="already takes the self-weight"):
        model.create_load_case("G2", self_weight=True)
    assert [case.name for case in model.load_cases] == ["Q", "G"]


def test_combinations_that_all_leave_the_self_weight_out_are_refused(tmp_path):
    model = _bare(_beam())
    # Q is id 1, so the case the solver would create is id 2.
    for attempt in (
        model.run_analysis,
        model.validate_schema,
        lambda: model.run_analysis_to_file(str(tmp_path / "out.json")),
    ):
        with pytest.raises(ValueError, match=r"\(id 2\)") as refusal:
            attempt()
        assert 'create_load_case("G", self_weight=True)' in str(refusal.value)
    assert not (tmp_path / "out.json").exists()


def test_validate_false_solves_and_the_solver_warns_on_each_combination():
    model = _bare(_beam())
    model.create_load_combination("SLS", {model.load_cases[0]: 1.0}, limit_state="SLS")
    model.run_analysis(validate=False)
    for name in ("ULS", "SLS"):
        warnings = (model.resultsbundle.loadcombinations[name].errors_and_warnings or {}).get("warnings")
        assert [w["code"] for w in warnings or []] == [CODE], name
    # The numbers are those without self-weight, which is what the warning says.
    uls = model.resultsbundle.loadcombinations["ULS"]
    assert _vertical_reaction(uls) == pytest.approx(1.5 * IMPOSED * SPAN, rel=1e-9)


def test_a_model_without_combinations_is_not_refused():
    model = _beam()
    model.settings.analysis_options.enable_self_weight = True
    model.run_analysis()
    self_weight = model.resultsbundle.loadcases["Self-weight"]
    assert _vertical_reaction(self_weight) == pytest.approx(_beam_weight(model), rel=1e-6)


def _document(enable=True, named=None, factors=((1, 1.5),)):
    options = {"enable_self_weight": enable}
    if named is not None:
        options["self_weight_load_case_id"] = named
    return {
        "analysis": {
            "options": options,
            "load_cases": [{"id": 1, "name": "Q"}, {"id": 3, "name": "G"}],
            "load_combinations": [
                {"id": 1, "load_case_factors": [{"load_case_id": c, "factor": f} for c, f in factors]}
            ],
        }
    }


def test_the_rule_reads_the_document_as_the_solver_does():
    # Without an id the solver creates the case with the highest id + 1: here 4.
    assert "(id 4)" in self_weight_outside_combinations(_document())
    assert self_weight_outside_combinations(_document(factors=((1, 1.5), (4, 1.35)))) is None
    # A factor of 0 is a choice, not an omission.
    assert self_weight_outside_combinations(_document(factors=((1, 1.5), (4, 0.0)))) is None
    assert self_weight_outside_combinations(_document(named=3, factors=((3, 1.35),))) is None
    assert "load case 3" in self_weight_outside_combinations(_document(named=3))
    assert self_weight_outside_combinations(_document(enable=False)) is None
    no_combinations = _document()
    no_combinations["analysis"]["load_combinations"] = []
    assert self_weight_outside_combinations(no_combinations) is None
