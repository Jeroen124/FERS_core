"""The older enum spellings `fers validate` lets through are exactly the engine's.

`ENGINE_ALIASES` is hand-written, because the engine's serde aliases are not in
its OpenAPI contract. The pinned engine is its own witness: given a value it does
not know, it names every spelling it accepts. Each enum's list must equal the
generated schema's values plus the table's aliases, so an alias the engine adds
or drops fails here when the pin moves.
"""

import json
import re

import fers_calculations
import pytest

from fers_core.builders import create_beam
from fers_core.settings.engine_aliases import ENGINE_ALIASES
from fers_core.types import pydantic_models

BOGUS = "__no_such_value__"


def _set(*path):
    def setter(document):
        node = document
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = BOGUS

    return setter


def _put(*path, value):
    # serde reads keys in document order, so an object holding only the probed
    # key fails on that value before it can miss a required sibling.
    def setter(document):
        node = document
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = json.loads(json.dumps(value).replace('"?"', json.dumps(BOGUS)))

    return setter


PROBES = {
    "AnalysisOrder": _set("analysis", "options", "order"),
    "RigidStrategy": _set("analysis", "options", "rigid_strategy"),
    "NonlinearMethod": _set("analysis", "options", "nonlinear_method"),
    "PdeltaFormulation": _set("analysis", "options", "pdelta_formulation"),
    "PdeltaMode": _set("analysis", "options", "pdelta_mode"),
    "Dimensionality": _set("analysis", "options", "dimensionality"),
    "MassFormulation": _put("analysis", "modal", value={"mass_formulation": "?"}),
    "SeismicMethod": _put("analysis", "seismic", value={"method": "?"}),
    "ModalCombination": _put("analysis", "seismic", value={"modal_combination": "?"}),
    "DirectionalCombination": _put("analysis", "seismic", value={"directional_combination": "?"}),
    "SpectrumType": _put(
        "analysis", "seismic", value={"spectrum_x": {"EurocodeParametric": {"spectrum_type": "?"}}}
    ),
    "ForceUnit": _set("settings", "unit_settings", "forceUnit"),
    "PressureUnit": _set("settings", "unit_settings", "pressureUnit"),
    "SupportConditionType": _set("model", "nodal_supports", 0, "X", "condition_type"),
    "LoadAxes": lambda d: d["analysis"]["load_cases"][0].__setitem__(
        "member_point_loads",
        [{"axes": BOGUS, "id": 1, "member": 1, "position": 0.5, "direction": [0, -1, 0], "magnitude": 1.0}],
    ),
}


@pytest.fixture(scope="module")
def beam_document(tmp_path_factory):
    path = tmp_path_factory.mktemp("aliases") / "beam.json"
    create_beam(5.0, "IPE180", udl=5000.0).save_to_json(str(path))
    return json.loads(path.read_text(encoding="utf-8"))


def _schema_values(name):
    return {member.value for member in getattr(pydantic_models, name)}


def test_every_alias_maps_to_a_schema_value_of_its_own_enum():
    for name, aliases in ENGINE_ALIASES.items():
        values = _schema_values(name)
        assert set(aliases.values()) <= values, name
        assert not set(aliases) & values, f"{name}: an alias is already a schema value"


def test_each_enum_is_found_by_its_set_of_schema_values():
    sets = [frozenset(_schema_values(name)) for name in ENGINE_ALIASES]
    assert len(set(sets)) == len(sets)


def test_every_table_entry_has_a_probe():
    assert set(PROBES) == set(ENGINE_ALIASES)


@pytest.mark.parametrize("name", sorted(PROBES))
def test_the_engine_accepts_exactly_the_schema_values_and_the_aliases(name, beam_document):
    document = json.loads(json.dumps(beam_document))
    PROBES[name](document)
    with pytest.raises(Exception) as refused:
        fers_calculations.calculate_from_json(json.dumps(document))
    message = str(refused.value)
    found = re.search(rf"unknown variant `{BOGUS}`, expected (.*?) at line", message)
    assert found, message.splitlines()[0]
    accepted = set(re.findall(r"`([^`]*)`", found.group(1)))
    assert accepted == _schema_values(name) | set(ENGINE_ALIASES[name])
