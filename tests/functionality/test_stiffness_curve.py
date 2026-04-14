"""Tests for the stiffness curve support condition (new API: Spring + StiffnessCurveConfig)."""

import pytest

from fers_core.supports.stiffness_curve import ForceComponent, StiffnessCurveConfig
from fers_core.supports.supportcondition import SupportCondition, SupportConditionType
from fers_core.supports.nodalsupport import NodalSupport
from fers_core.members.memberhinge import MemberHinge


# ── StiffnessCurveConfig Validation ───────────────────────────────────────────


class TestStiffnessCurveConfigValidation:
    def test_valid_config(self):
        cfg = StiffnessCurveConfig(ForceComponent.Vz, [[0, 1e5], [100_000, 1e8]])
        assert cfg.depends_on == ForceComponent.Vz
        assert len(cfg.points) == 2

    def test_too_few_points_raises(self):
        with pytest.raises(ValueError, match="at least 2"):
            StiffnessCurveConfig(ForceComponent.Vz, [[0, 1e5]])

    def test_negative_stiffness_raises(self):
        with pytest.raises(ValueError, match="non-negative"):
            StiffnessCurveConfig(ForceComponent.Vz, [[0, -100], [10, 200]])

    def test_unsorted_points_raises(self):
        with pytest.raises(ValueError, match="sorted"):
            StiffnessCurveConfig(ForceComponent.Vz, [[50, 100], [10, 200]])

    def test_wrong_point_length_raises(self):
        with pytest.raises(ValueError, match="exactly 2 values"):
            StiffnessCurveConfig(ForceComponent.Vz, [[0, 1e5, 99], [10, 200]])

    def test_many_points(self):
        points = [[i * 10, 1e5 + i * 1e3] for i in range(10)]
        cfg = StiffnessCurveConfig(ForceComponent.N, points)
        assert len(cfg.points) == 10
        assert cfg.depends_on == ForceComponent.N

    def test_all_force_components(self):
        for fc in ForceComponent:
            cfg = StiffnessCurveConfig(fc, [[0, 100], [10, 200]])
            assert cfg.depends_on == fc


# ── StiffnessCurveConfig Serialization ────────────────────────────────────────


class TestStiffnessCurveConfigSerialization:
    def test_to_dict(self):
        cfg = StiffnessCurveConfig(ForceComponent.My, [[0, 1e5], [50000, 1e7]])
        d = cfg.to_dict()
        assert d == {"depends_on": "My", "points": [[0, 1e5], [50000, 1e7]]}

    def test_from_dict_new_format(self):
        data = {"depends_on": "Vz", "points": [[0, 1e5], [50000, 1e7]]}
        cfg = StiffnessCurveConfig.from_dict(data)
        assert cfg.depends_on == ForceComponent.Vz
        assert cfg.points == [[0, 1e5], [50000, 1e7]]

    def test_from_dict_legacy_list(self):
        """Legacy format: bare list → wrapped with ForceComponent.Vz."""
        data = [[0, 1e5], [50000, 1e7]]
        cfg = StiffnessCurveConfig.from_dict(data)
        assert cfg.depends_on == ForceComponent.Vz
        assert cfg.points == [[0, 1e5], [50000, 1e7]]

    def test_from_dict_none(self):
        assert StiffnessCurveConfig.from_dict(None) is None

    def test_round_trip(self):
        original = StiffnessCurveConfig(ForceComponent.Mx, [[0, 500], [10, 5000]])
        restored = StiffnessCurveConfig.from_dict(original.to_dict())
        assert restored == original

    def test_equality(self):
        a = StiffnessCurveConfig(ForceComponent.Vz, [[0, 100], [10, 200]])
        b = StiffnessCurveConfig(ForceComponent.Vz, [[0, 100], [10, 200]])
        assert a == b

    def test_inequality_different_depends_on(self):
        a = StiffnessCurveConfig(ForceComponent.Vz, [[0, 100], [10, 200]])
        b = StiffnessCurveConfig(ForceComponent.N, [[0, 100], [10, 200]])
        assert a != b


# ── SupportCondition — spring_curve Factory ───────────────────────────────────


class TestSpringCurveCreation:
    def test_create_spring_curve(self):
        sc = SupportCondition.spring_curve(ForceComponent.Vz, [[0, 1e5], [100_000, 1e8]])
        assert sc.condition_type == SupportConditionType.SPRING
        assert sc.stiffness is None
        assert sc.stiffness_curve is not None
        assert sc.stiffness_curve.depends_on == ForceComponent.Vz
        assert len(sc.stiffness_curve.points) == 2

    def test_create_spring_curve_with_different_component(self):
        sc = SupportCondition.spring_curve(ForceComponent.My, [[0, 1e5], [100_000, 1e8]])
        assert sc.stiffness_curve.depends_on == ForceComponent.My

    def test_convenience_stiffness_curve_factory(self):
        """Old factory defaults to ForceComponent.Vz."""
        sc = SupportCondition.stiffness_curve([[0, 1e5], [100_000, 1e8]])
        assert sc.condition_type == SupportConditionType.SPRING
        assert sc.stiffness_curve.depends_on == ForceComponent.Vz

    def test_curve_on_non_spring_type_raises(self):
        curve = StiffnessCurveConfig(ForceComponent.Vz, [[0, 1e5], [100, 1e6]])
        with pytest.raises(ValueError, match="must not specify stiffness_curve"):
            SupportCondition(SupportConditionType.FIXED, stiffness_curve=curve)

    def test_spring_without_stiffness_or_curve_raises(self):
        with pytest.raises(ValueError, match="requires a positive stiffness"):
            SupportCondition(SupportConditionType.SPRING)

    def test_spring_with_curve_and_stiffness(self):
        """Both stiffness and curve on SPRING is allowed — curve overrides."""
        curve = StiffnessCurveConfig(ForceComponent.Vz, [[0, 1e5], [100, 1e6]])
        sc = SupportCondition(SupportConditionType.SPRING, stiffness=5e4, stiffness_curve=curve)
        assert sc.stiffness == 5e4
        assert sc.stiffness_curve is not None


# ── SupportCondition Serialization ────────────────────────────────────────────


class TestSpringCurveSerialization:
    def test_to_dict(self):
        sc = SupportCondition.spring_curve(ForceComponent.Vz, [[0, 1e5], [50000, 1e7]])
        d = sc.to_dict()
        assert d["condition_type"] == "Spring"
        assert d["stiffness"] is None
        assert d["stiffness_curve"] == {"depends_on": "Vz", "points": [[0, 1e5], [50000, 1e7]]}

    def test_from_dict_new_format(self):
        data = {
            "condition_type": "Spring",
            "stiffness": None,
            "stiffness_curve": {"depends_on": "Vz", "points": [[0, 1e5], [50000, 1e7]]},
        }
        sc = SupportCondition.from_dict(data)
        assert sc.condition_type == SupportConditionType.SPRING
        assert sc.stiffness_curve.depends_on == ForceComponent.Vz
        assert sc.stiffness_curve.points == [[0, 1e5], [50000, 1e7]]

    def test_from_dict_legacy_stiffnesscurve_type(self):
        """Legacy JSON with condition_type='StiffnessCurve' maps to SPRING + Vz."""
        data = {
            "condition_type": "StiffnessCurve",
            "stiffness": None,
            "stiffness_curve": [[0, 1e5], [50000, 1e7]],
        }
        sc = SupportCondition.from_dict(data)
        assert sc.condition_type == SupportConditionType.SPRING
        assert sc.stiffness_curve.depends_on == ForceComponent.Vz
        assert sc.stiffness_curve.points == [[0, 1e5], [50000, 1e7]]

    def test_round_trip(self):
        original = SupportCondition.spring_curve(ForceComponent.Mx, [[0, 500], [10, 5000], [100, 50000]])
        restored = SupportCondition.from_dict(original.to_dict())
        assert restored.condition_type == original.condition_type
        assert restored.stiffness_curve == original.stiffness_curve
        assert restored.stiffness == original.stiffness

    def test_from_dict_case_variants(self):
        for name in ("StiffnessCurve", "stiffnesscurve", "stiffness-curve"):
            data = {"condition_type": name, "stiffness_curve": [[0, 100], [10, 200]]}
            sc = SupportCondition.from_dict(data)
            assert sc.condition_type == SupportConditionType.SPRING
            assert sc.stiffness_curve is not None


# ── Display ───────────────────────────────────────────────────────────────────


class TestSpringCurveDisplay:
    def test_display_string(self):
        sc = SupportCondition.spring_curve(ForceComponent.Vz, [[0, 1e5], [50000, 1e7]])
        s = sc.to_display_string()
        assert "Spring curve" in s
        assert "2 points" in s
        assert "Vz" in s

    def test_repr(self):
        sc = SupportCondition.spring_curve(ForceComponent.Vz, [[0, 1e5], [50000, 1e7]])
        r = repr(sc)
        assert "Spring" in r
        assert "2 points" in r
        assert "Vz" in r


# ── NodalSupport Integration ──────────────────────────────────────────────────


class TestNodalSupportSpringCurve:
    def test_explicit_condition(self):
        ns = NodalSupport(
            rotation_conditions={
                "Y": SupportCondition.spring_curve(ForceComponent.Vz, [[0, 1e5], [100_000, 1e8]]),
            }
        )
        assert ns.rotation_conditions["Y"].condition_type == SupportConditionType.SPRING
        assert ns.rotation_conditions["Y"].stiffness_curve is not None
        assert ns.rotation_conditions["X"].condition_type == SupportConditionType.FIXED  # default

    def test_list_shorthand(self):
        """Passing a list to NodalSupport creates a spring_curve with Vz default."""
        ns = NodalSupport(
            rotation_conditions={
                "Z": [[0, 1e5], [50_000, 1e7], [100_000, 1e8]],
            }
        )
        assert ns.rotation_conditions["Z"].condition_type == SupportConditionType.SPRING
        assert ns.rotation_conditions["Z"].stiffness_curve.depends_on == ForceComponent.Vz
        assert len(ns.rotation_conditions["Z"].stiffness_curve.points) == 3

    def test_string_stiffnesscurve_raises(self):
        with pytest.raises(ValueError, match="stiffness curve requires data"):
            NodalSupport(rotation_conditions={"Y": "StiffnessCurve"})

    def test_string_spring_curve_raises(self):
        with pytest.raises(ValueError, match="stiffness curve requires data"):
            NodalSupport(rotation_conditions={"Y": "spring_curve"})

    def test_to_dict_round_trip(self):
        ns = NodalSupport(
            id=42,
            rotation_conditions={
                "Y": SupportCondition.spring_curve(ForceComponent.Vz, [[0, 1e5], [100_000, 1e8]]),
                "Z": SupportCondition.free(),
            },
        )
        d = ns.to_dict()
        assert d["rotation_conditions"]["Y"]["condition_type"] == "Spring"
        assert d["rotation_conditions"]["Y"]["stiffness_curve"] == {
            "depends_on": "Vz",
            "points": [[0, 1e5], [100_000, 1e8]],
        }

        ns2 = NodalSupport.from_dict(d)
        assert ns2.rotation_conditions["Y"].condition_type == SupportConditionType.SPRING
        assert ns2.rotation_conditions["Y"].stiffness_curve.depends_on == ForceComponent.Vz
        assert ns2.rotation_conditions["Y"].stiffness_curve.points == [[0, 1e5], [100_000, 1e8]]
        assert ns2.rotation_conditions["Z"].condition_type == SupportConditionType.FREE


# ── MemberHinge Integration ───────────────────────────────────────────────────


class TestMemberHingeStiffnessCurve:
    def test_create_with_stiffness_curves(self):
        MemberHinge.reset_counter()
        curve_my = StiffnessCurveConfig(ForceComponent.N, [[0, 1e5], [50_000, 1e7]])
        curve_mz = StiffnessCurveConfig(ForceComponent.Vy, [[0, 2e5], [30_000, 2e7]])
        hinge = MemberHinge(
            rotational_release_my=1e6,
            stiffness_curve_my=curve_my,
            stiffness_curve_mz=curve_mz,
        )
        assert hinge.stiffness_curve_my == curve_my
        assert hinge.stiffness_curve_mz == curve_mz
        assert hinge.stiffness_curve_vx is None

    def test_to_dict_with_curves(self):
        MemberHinge.reset_counter()
        curve = StiffnessCurveConfig(ForceComponent.N, [[0, 1e5], [50_000, 1e7]])
        hinge = MemberHinge(stiffness_curve_my=curve)
        d = hinge.to_dict()
        assert d["stiffness_curve_my"] == {"depends_on": "N", "points": [[0, 1e5], [50_000, 1e7]]}
        assert d["stiffness_curve_vx"] is None
        assert d["stiffness_curve_mz"] is None

    def test_to_dict_without_curves(self):
        MemberHinge.reset_counter()
        hinge = MemberHinge(rotational_release_mz=0.0)
        d = hinge.to_dict()
        assert d["stiffness_curve_vx"] is None
        assert d["stiffness_curve_mz"] is None

    def test_from_dict_with_curves(self):
        data = {
            "id": 1,
            "hinge_type": "",
            "stiffness_curve_vz": {"depends_on": "Mx", "points": [[0, 500], [100, 5000]]},
        }
        hinge = MemberHinge.from_dict(data)
        assert hinge.stiffness_curve_vz is not None
        assert hinge.stiffness_curve_vz.depends_on == ForceComponent.Mx
        assert hinge.stiffness_curve_vz.points == [[0, 500], [100, 5000]]
        assert hinge.stiffness_curve_my is None

    def test_from_dict_without_curves(self):
        data = {"id": 1, "hinge_type": "", "rotational_release_mz": 0.0}
        hinge = MemberHinge.from_dict(data)
        assert hinge.stiffness_curve_vx is None
        assert hinge.stiffness_curve_mz is None

    def test_round_trip(self):
        MemberHinge.reset_counter()
        curve = StiffnessCurveConfig(ForceComponent.Vz, [[0, 1e3], [1000, 1e6]])
        original = MemberHinge(
            rotational_release_my=1e5,
            stiffness_curve_my=curve,
        )
        restored = MemberHinge.from_dict(original.to_dict())
        assert restored.stiffness_curve_my == original.stiffness_curve_my
        assert restored.rotational_release_my == original.rotational_release_my
        assert restored.stiffness_curve_vx is None


# ── Backward Compatibility ────────────────────────────────────────────────────


class TestBackwardCompatibility:
    """Existing condition types must continue to work exactly as before."""

    def test_fixed(self):
        sc = SupportCondition.fixed()
        assert sc.condition_type == SupportConditionType.FIXED
        assert sc.stiffness_curve is None
        d = sc.to_dict()
        assert "stiffness_curve" not in d

    def test_spring(self):
        sc = SupportCondition.spring(1e6)
        assert sc.stiffness == 1e6
        assert sc.stiffness_curve is None

    def test_from_dict_without_curve_field(self):
        """Old JSON without stiffness_curve field should still work."""
        data = {"condition_type": "Fixed", "stiffness": None}
        sc = SupportCondition.from_dict(data)
        assert sc.condition_type == SupportConditionType.FIXED
        assert sc.stiffness_curve is None

    def test_convenience_stiffness_curve_factory_compat(self):
        """The old SupportCondition.stiffness_curve() factory still works."""
        sc = SupportCondition.stiffness_curve([[0, 1e5], [50000, 1e7]])
        assert sc.condition_type == SupportConditionType.SPRING
        assert sc.stiffness_curve.depends_on == ForceComponent.Vz
        assert sc.stiffness_curve.points == [[0, 1e5], [50000, 1e7]]
