"""AnalysisOptions P-delta / nonlinear-method modelling (feedback item 05).

The Rust solver honours `nonlinear_method`, `pdelta_mode`, `pdelta_formulation`
and `pdelta_suppress_axes` on the wire, but the Python AnalysisOptions could not
express them. They are now optional constructor args, emitted only when set, and
parsed back by from_dict(). `solver` is now emitted too.
"""

from fers_core.settings.anlysis_options import AnalysisOptions
from fers_core.settings.enums import (
    AnalysisOrder,
    NonlinearMethod,
    PdeltaFormulation,
    PdeltaMode,
)


def test_defaults_omit_pdelta_fields():
    """Unset P-delta controls are not emitted, so the solver keeps its defaults."""
    d = AnalysisOptions().to_dict()
    assert "nonlinear_method" not in d
    assert "pdelta_mode" not in d
    assert "pdelta_formulation" not in d
    assert "pdelta_suppress_axes" not in d
    # solver is now part of the emitted contract.
    assert d["solver"] == "newton_raphson"


def test_emits_pdelta_fields_when_set():
    opts = AnalysisOptions(
        order=AnalysisOrder.NONLINEAR,
        nonlinear_method=NonlinearMethod.P_DELTA,
        pdelta_mode=PdeltaMode.IN_PLANE_ONLY,
        pdelta_formulation=PdeltaFormulation.SIMPLIFIED,
        pdelta_suppress_axes=["Z"],
    )
    d = opts.to_dict()
    # Wire strings must match the Rust serde spellings exactly.
    assert d["nonlinear_method"] == "P_DELTA"
    assert d["pdelta_mode"] == "IN_PLANE_ONLY"
    assert d["pdelta_formulation"] == "SIMPLIFIED"
    assert d["pdelta_suppress_axes"] == ["Z"]


def test_round_trip_pdelta_fields():
    opts = AnalysisOptions(
        nonlinear_method=NonlinearMethod.P_DELTA,
        pdelta_mode=PdeltaMode.IN_PLANE_ONLY,
        pdelta_formulation=PdeltaFormulation.CONSISTENT,
        pdelta_suppress_axes=["X", "Z"],
    )
    restored = AnalysisOptions.from_dict(opts.to_dict())
    assert restored.nonlinear_method == NonlinearMethod.P_DELTA
    assert restored.pdelta_mode == PdeltaMode.IN_PLANE_ONLY
    assert restored.pdelta_formulation == PdeltaFormulation.CONSISTENT
    assert restored.pdelta_suppress_axes == ["X", "Z"]


def test_from_dict_absent_pdelta_is_none():
    restored = AnalysisOptions.from_dict({"order": "NONLINEAR"})
    assert restored.nonlinear_method is None
    assert restored.pdelta_mode is None
    assert restored.pdelta_formulation is None
    assert restored.pdelta_suppress_axes is None


def test_from_dict_accepts_enum_names_and_values():
    # by value
    a = AnalysisOptions.from_dict({"pdelta_mode": "IN_PLANE_ONLY"})
    assert a.pdelta_mode == PdeltaMode.IN_PLANE_ONLY
    # by name
    b = AnalysisOptions.from_dict({"pdelta_mode": "FULL"})
    assert b.pdelta_mode == PdeltaMode.FULL
