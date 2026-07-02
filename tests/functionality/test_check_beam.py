"""Coverage for the check_beam EC3 builder (fers_core.builders)."""

import pytest

from fers_core import check_beam


def _governing_rows(beam):
    """Run the model and return (result, {row-label: value}) for the governing entity."""
    beam.run_analysis()
    res = beam.unity_check_results()
    assert res, "expected a unity-check result"
    u = res[0]
    gov = u["governing"] if isinstance(u, dict) else u.governing
    trace = (gov.get("trace") if isinstance(gov, dict) else gov.trace) or []
    rows = {}
    for st in trace:
        lbl = st.get("label") if isinstance(st, dict) else st.label
        val = st.get("value") if isinstance(st, dict) else st.value
        if isinstance(val, (int, float)):
            rows[lbl] = val
    return u, rows


def test_ec3_bending_matches_hand_calc():
    # IPE300, 6 m, S235, simply supported, UDL 10 kN/m, gamma_G = 1.35.
    # MEd = 1.35*10*36/8 = 60.75 kNm; Mc,Rd = wpl_z*fy = 6.28e-4*235e6 = 147.6 kNm.
    beam = check_beam(6.0, "IPE300", material="S235", support="simply_supported", udl=10000.0)
    _u, rows = _governing_rows(beam)
    bending_z = rows.get("Bending z (6.2.5)")
    assert bending_z is not None
    assert bending_z == pytest.approx(60.75 / 147.6, rel=0.03)  # ~0.412


def test_ec3_ltb_governs_unrestrained_beam():
    # A 6 m unrestrained IPE300 gravity beam: lateral-torsional buckling (§6.3.2)
    # governs over pure cross-section bending. Requires fers_calculations >= 0.2.42
    # (the major-axis LTB fix); an older solver reports LTB as 0.
    beam = check_beam(6.0, "IPE300", material="S235", support="simply_supported", udl=10000.0)
    _u, rows = _governing_rows(beam)
    ltb = rows.get("LTB (6.3.2)")
    bending = rows.get("Bending z (6.2.5)")
    assert ltb is not None and ltb > 0.0, f"LTB should fire on the strong axis (got {ltb})"
    assert ltb > bending, f"LTB should govern over cross-section bending ({ltb} vs {bending})"
    assert rows.get("Governing") == pytest.approx(ltb, rel=1e-6)


def test_ec3_check_id_and_schema_gate():
    # from_name section + fixed supports; validate_schema also exercises the
    # LoadCombination limit_state serialization (regression guard).
    beam = check_beam(4.0, "HEA200", material="S355", support="fixed", udl=20000.0)
    beam.validate_schema()
    u, _rows = _governing_rows(beam)
    check_id = u["check_id"] if isinstance(u, dict) else u.check_id
    assert check_id == "ec3"


def test_point_load_and_grade():
    beam = check_beam(5.0, "IPE400", support="simply_supported", point_load=30000.0)
    u, rows = _governing_rows(beam)
    assert (rows.get("Governing") or 0) > 0


def test_invalid_inputs_raise():
    with pytest.raises(ValueError):
        check_beam(-1.0, "IPE200")
    with pytest.raises(ValueError):
        check_beam(3.0, "IPE200", support="floating")
