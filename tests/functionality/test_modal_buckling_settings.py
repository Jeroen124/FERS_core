"""First-class modal/buckling analysis settings: exact wire shapes, reference
normalization, round-trips, and schema conformance of a full model.

The wire contract (verified against the solver source):
- ``analysis.modal``    = ``{"num_modes", "mass_formulation", "tolerance"?, "max_iterations"?}``
  with ``mass_formulation`` emitted UPPERCASE (``"CONSISTENT"``/``"LUMPED"`` —
  the solver also takes titlecase via serde aliases, but the generated pydantic
  input schema only accepts the uppercase tokens).
- ``analysis.buckling`` = ``{"num_modes", "reference", "tolerance"?, "max_iterations"?}``
  where ``reference`` is externally tagged: ``{"LoadCase": id}`` or
  ``{"LoadCombination": id}``.
- Optionals are OMITTED when unset (Rust ``skip_serializing_if``).
"""

import pytest

from fers_core import (
    FERS,
    BucklingAnalysisSettings,
    LoadCombination,
    MassFormulation,
    Member,
    MemberSet,
    ModalAnalysisSettings,
    NodalLoad,
    NodalSupport,
    Node,
)
from tests.common_functions import build_steel_s235, build_ipe180


def _beam() -> FERS:
    steel = build_steel_s235()
    sec = build_ipe180(steel)
    m = FERS()
    n1 = Node(0.0, 0.0, 0.0)
    n2 = Node(5.0, 0.0, 0.0)
    n1.nodal_support = NodalSupport()
    mem = Member(start_node=n1, end_node=n2, section=sec)
    m.add_member_set(MemberSet(members=[mem]))
    lc = m.create_load_case(name="LC")
    NodalLoad(node=n2, load_case=lc, magnitude=1000.0, direction=(0.0, -1.0, 0.0))
    return m


# --- exact wire shapes -------------------------------------------------------


def test_modal_default_wire_shape():
    settings = ModalAnalysisSettings(num_modes=6)
    assert settings.to_dict() == {"num_modes": 6, "mass_formulation": "CONSISTENT"}


def test_modal_full_wire_shape():
    settings = ModalAnalysisSettings(
        num_modes=12,
        mass_formulation=MassFormulation.LUMPED,
        tolerance=1e-8,
        max_iterations=200,
    )
    assert settings.to_dict() == {
        "num_modes": 12,
        "mass_formulation": "LUMPED",
        "tolerance": 1e-8,
        "max_iterations": 200,
    }


def test_modal_mass_formulation_accepts_strings_and_normalizes_uppercase():
    # Titlecase passes the Rust solver via a serde alias but FAILS the generated
    # pydantic input schema — the builder must normalize to the uppercase token.
    for raw in ("Consistent", "CONSISTENT", "consistent", MassFormulation.CONSISTENT):
        assert ModalAnalysisSettings(6, mass_formulation=raw).to_dict()["mass_formulation"] == ("CONSISTENT")
    assert ModalAnalysisSettings(6, mass_formulation="Lumped").to_dict()["mass_formulation"] == "LUMPED"
    with pytest.raises(ValueError, match="mass_formulation"):
        ModalAnalysisSettings(6, mass_formulation="Diagonal")


def test_modal_mass_formulation_none_is_omitted():
    settings = ModalAnalysisSettings(num_modes=3, mass_formulation=None)
    assert settings.to_dict() == {"num_modes": 3}


def test_modal_num_modes_must_be_positive():
    with pytest.raises(ValueError, match="num_modes"):
        ModalAnalysisSettings(num_modes=0)


def test_buckling_wire_shape_optionals_absent():
    settings = BucklingAnalysisSettings(reference=("LoadCase", 3), num_modes=4)
    assert settings.to_dict() == {"num_modes": 4, "reference": {"LoadCase": 3}}


def test_buckling_wire_shape_full():
    settings = BucklingAnalysisSettings(
        reference={"LoadCombination": 2},
        num_modes=2,
        tolerance=1e-7,
        max_iterations=50,
    )
    assert settings.to_dict() == {
        "num_modes": 2,
        "reference": {"LoadCombination": 2},
        "tolerance": 1e-7,
        "max_iterations": 50,
    }


# --- buckling reference normalization ----------------------------------------


def test_buckling_reference_accepts_load_case_object():
    m = _beam()
    lc = m.load_cases[0]
    settings = BucklingAnalysisSettings(reference=lc)
    assert settings.to_dict()["reference"] == {"LoadCase": lc.id}


def test_buckling_reference_accepts_load_combination_object():
    m = _beam()
    comb = LoadCombination(name="ULS", load_cases_factors={m.load_cases[0]: 1.5})
    m.add_load_combination(comb)
    settings = BucklingAnalysisSettings(reference=comb)
    assert settings.to_dict()["reference"] == {"LoadCombination": comb.id}


def test_buckling_reference_accepts_tagged_dict_and_tuples():
    assert BucklingAnalysisSettings({"LoadCase": 7}).to_dict()["reference"] == {"LoadCase": 7}
    assert BucklingAnalysisSettings(("load_case", 7)).to_dict()["reference"] == {"LoadCase": 7}
    assert BucklingAnalysisSettings(("LoadCombination", 9)).to_dict()["reference"] == {"LoadCombination": 9}
    assert BucklingAnalysisSettings(("load_combination", 9)).to_dict()["reference"] == {"LoadCombination": 9}


def test_buckling_reference_rejects_invalid_forms():
    with pytest.raises(ValueError, match="externally tagged"):
        BucklingAnalysisSettings({"load_case": 1})
    with pytest.raises(ValueError, match="reference kind"):
        BucklingAnalysisSettings(("Node", 1))
    with pytest.raises(TypeError, match="reference"):
        BucklingAnalysisSettings(3.14)


# --- settings round-trips -----------------------------------------------------


def test_modal_settings_from_dict_round_trip():
    original = {"num_modes": 8, "mass_formulation": "LUMPED", "tolerance": 1e-9}
    assert ModalAnalysisSettings.from_dict(original).to_dict() == original
    minimal = {"num_modes": 2}
    assert ModalAnalysisSettings.from_dict(minimal).to_dict() == minimal


def test_buckling_settings_from_dict_round_trip():
    original = {"num_modes": 3, "reference": {"LoadCombination": 4}, "max_iterations": 40}
    assert BucklingAnalysisSettings.from_dict(original).to_dict() == original


# --- FERS document integration ------------------------------------------------


def test_plain_model_omits_modal_and_buckling_keys():
    d = _beam().to_dict(include_results=False)
    assert "modal" not in d["analysis"]
    assert "buckling" not in d["analysis"]


def test_model_emits_modal_and_buckling_and_conforms_to_schema():
    m = _beam()
    m.analysis.modal = ModalAnalysisSettings(num_modes=6)
    m.analysis.buckling = BucklingAnalysisSettings(reference=m.load_cases[0], num_modes=2)

    d = m.to_dict(include_results=False)
    assert d["analysis"]["modal"] == {"num_modes": 6, "mass_formulation": "CONSISTENT"}
    assert d["analysis"]["buckling"] == {
        "num_modes": 2,
        "reference": {"LoadCase": m.load_cases[0].id},
    }
    # The full document must pass the repo's schema gate (generated pydantic
    # FERS input model — single source of truth from the solver's OpenAPI).
    m.validate_schema()


def test_fers_document_round_trip_preserves_modal_and_buckling():
    m = _beam()
    m.analysis.modal = ModalAnalysisSettings(num_modes=5, tolerance=1e-7)
    m.analysis.buckling = BucklingAnalysisSettings(
        reference=("LoadCase", m.load_cases[0].id), num_modes=3, max_iterations=80
    )
    d = m.to_dict(include_results=False)

    rebuilt = FERS.from_dict(d)
    assert isinstance(rebuilt.analysis.modal, ModalAnalysisSettings)
    assert isinstance(rebuilt.analysis.buckling, BucklingAnalysisSettings)
    d2 = rebuilt.to_dict(include_results=False)
    assert d2["analysis"]["modal"] == d["analysis"]["modal"]
    assert d2["analysis"]["buckling"] == d["analysis"]["buckling"]
    rebuilt.validate_schema()


# --- end-to-end modal solve ----------------------------------------------------


def test_end_to_end_modal_solve_on_cantilever():
    """Solve a tiny cantilever through the installed fers_calculations wheel and
    assert a positive fundamental frequency lands in the results bundle."""
    try:
        import fers_calculations  # noqa: F401
    except ImportError:
        pytest.skip("fers_calculations wheel is not installed")

    m = _beam()  # cantilever: fixed at n1, free at n2
    m.analysis.modal = ModalAnalysisSettings(num_modes=3)
    m.run_analysis()  # validate=True: exercises the schema gate on the real path

    modal = m.resultsbundle.modal
    if modal is None:
        pytest.skip("installed fers_calculations wheel does not return modal results")
    modes = modal["modes"]
    assert len(modes) == 3
    fundamental = modes[0]["natural_frequency"]
    assert fundamental > 0.0
    # Modes come back sorted lowest-frequency first.
    freqs = [mode["natural_frequency"] for mode in modes]
    assert freqs == sorted(freqs)
