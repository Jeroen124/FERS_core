"""Authoring + round-trip coverage for unity checks in the Python API."""

from fers_core import FERS
from fers_core.unity_checks import (
    generic_check,
    ec3_steel_check,
    var,
    member_force,
    section,
    material,
    expr,
    all_members,
)


def test_unity_checks_serialize_into_analysis():
    calc = FERS()
    calc.add_unity_check(
        generic_check(
            "bending_stress",
            "Bending stress",
            variables=[
                var("M", member_force("My", "MaxAbs")),
                var("c", expr("h / 2")),
                var("h", section("H")),
                var("I", section("Iy")),
                var("fy", material("Fy")),
            ],
            demand="M * c / I",
            capacity="fy",
            applies_to=all_members(),
            limit_state="ULS",
        )
    )
    calc.analysis.add_unity_check(ec3_steel_check("ec3", "EC3 member", limit_state="ULS"))

    data = calc.to_dict(include_results=False)
    checks = data["analysis"]["unity_checks"]
    assert len(checks) == 2
    ids = {c["id"] for c in checks}
    assert ids == {"bending_stress", "ec3"}

    # exact wire shape for the generic spec
    gen = next(c for c in checks if c["id"] == "bending_stress")
    assert gen["applies_to"] == {"type": "AllMembers"}
    assert gen["spec"]["Generic"]["demand"] == "M * c / I"
    assert gen["spec"]["Generic"]["variables"][0]["source"]["Quantity"]["MemberForce"][
        "aggregation"
    ] == {"type": "MaxAbs"}

    ec3 = next(c for c in checks if c["id"] == "ec3")
    assert ec3["spec"]["Ec3Steel"]["include_buckling"] is True


def test_unity_checks_round_trip():
    calc = FERS()
    calc.add_unity_check(ec3_steel_check("ec3", "EC3 member"))
    data = calc.to_dict(include_results=False)
    rebuilt = FERS.from_dict(data)
    assert rebuilt.unity_checks == calc.unity_checks
    assert rebuilt.analysis.unity_checks[0]["id"] == "ec3"


def test_unity_results_accessors_default_empty():
    calc = FERS()
    assert calc.unity_check_results() == []
    assert calc.unity_report_html() is None
