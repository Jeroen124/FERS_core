"""
Tests for MaterialLibrary
==========================
All tests are self-contained — no solver or FEM dependency.

Checks:
  • Every factory method returns a valid Material instance.
  • Physical properties are in a plausible range (sanity bounds).
  • Group-specific constants match published references.
  • Registry helpers (list_available, get) work correctly.
  • Each call returns an independent object (separate ID / identity).
"""

import pytest

from fers_core.members.material import Material
from fers_core.members.material_library import MaterialLibrary


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ALL_FACTORIES = [
    # steel
    MaterialLibrary.S235,
    MaterialLibrary.S275,
    MaterialLibrary.S355,
    MaterialLibrary.S420,
    MaterialLibrary.S460,
    # stainless
    MaterialLibrary.stainless_304,
    MaterialLibrary.stainless_316,
    # aluminium
    MaterialLibrary.aluminum_6061_T6,
    MaterialLibrary.aluminum_7075_T6,
    MaterialLibrary.aluminum_2024_T3,
    MaterialLibrary.aluminum_5083,
    # titanium
    MaterialLibrary.titanium_grade2,
    MaterialLibrary.titanium_grade5,
    # copper family
    MaterialLibrary.copper,
    MaterialLibrary.brass,
    MaterialLibrary.bronze,
    # concrete
    MaterialLibrary.concrete_C20_25,
    MaterialLibrary.concrete_C25_30,
    MaterialLibrary.concrete_C30_37,
    MaterialLibrary.concrete_C35_45,
    # cast iron
    MaterialLibrary.cast_iron_grey,
    MaterialLibrary.cast_iron_ductile,
]

EXPECTED_TOTAL = 22  # update this when new materials are added


# ---------------------------------------------------------------------------
# 1. Return type and completeness
# ---------------------------------------------------------------------------


class TestReturnType:
    @pytest.mark.parametrize(
        "factory", ALL_FACTORIES, ids=lambda f: f.__name__ if hasattr(f, "__name__") else str(f)
    )
    def test_returns_material_instance(self, factory):
        assert isinstance(factory(), Material)

    def test_total_registered_count(self):
        assert len(MaterialLibrary.list_available()) == EXPECTED_TOTAL

    def test_list_available_is_sorted(self):
        names = MaterialLibrary.list_available()
        assert names == sorted(names)


# ---------------------------------------------------------------------------
# 2. Physical sanity — every material must have positive, non-zero values
# ---------------------------------------------------------------------------


class TestPhysicalSanity:
    @pytest.mark.parametrize(
        "factory", ALL_FACTORIES, ids=lambda f: f.__name__ if hasattr(f, "__name__") else str(f)
    )
    def test_e_mod_positive(self, factory):
        assert factory().e_mod > 0

    @pytest.mark.parametrize(
        "factory", ALL_FACTORIES, ids=lambda f: f.__name__ if hasattr(f, "__name__") else str(f)
    )
    def test_g_mod_positive(self, factory):
        assert factory().g_mod > 0

    @pytest.mark.parametrize(
        "factory", ALL_FACTORIES, ids=lambda f: f.__name__ if hasattr(f, "__name__") else str(f)
    )
    def test_density_positive(self, factory):
        assert factory().density > 0

    @pytest.mark.parametrize(
        "factory", ALL_FACTORIES, ids=lambda f: f.__name__ if hasattr(f, "__name__") else str(f)
    )
    def test_yield_stress_positive(self, factory):
        assert factory().yield_stress > 0

    @pytest.mark.parametrize(
        "factory", ALL_FACTORIES, ids=lambda f: f.__name__ if hasattr(f, "__name__") else str(f)
    )
    def test_g_mod_less_than_e_mod(self, factory):
        """Shear modulus must be less than Young's modulus for any isotropic material."""
        mat = factory()
        assert mat.g_mod < mat.e_mod

    @pytest.mark.parametrize(
        "factory", ALL_FACTORIES, ids=lambda f: f.__name__ if hasattr(f, "__name__") else str(f)
    )
    def test_name_is_non_empty_string(self, factory):
        assert isinstance(factory().name, str) and factory().name.strip()


# ---------------------------------------------------------------------------
# 3. Group-specific reference values
# ---------------------------------------------------------------------------


class TestSteelProperties:
    """EN 1993-1-1: E = 210 GPa, G = 81 GPa for all carbon-steel grades."""

    E_STEEL = 210e9
    G_STEEL = 81e9

    @pytest.mark.parametrize(
        "factory,fy",
        [
            (MaterialLibrary.S235, 235e6),
            (MaterialLibrary.S275, 275e6),
            (MaterialLibrary.S355, 355e6),
            (MaterialLibrary.S420, 420e6),
            (MaterialLibrary.S460, 460e6),
        ],
    )
    def test_yield_stress(self, factory, fy):
        assert factory().yield_stress == pytest.approx(fy)

    @pytest.mark.parametrize(
        "factory",
        [
            MaterialLibrary.S235,
            MaterialLibrary.S275,
            MaterialLibrary.S355,
            MaterialLibrary.S420,
            MaterialLibrary.S460,
        ],
    )
    def test_e_mod(self, factory):
        assert factory().e_mod == pytest.approx(self.E_STEEL)

    @pytest.mark.parametrize(
        "factory",
        [
            MaterialLibrary.S235,
            MaterialLibrary.S275,
            MaterialLibrary.S355,
            MaterialLibrary.S420,
            MaterialLibrary.S460,
        ],
    )
    def test_g_mod(self, factory):
        assert factory().g_mod == pytest.approx(self.G_STEEL)

    @pytest.mark.parametrize(
        "factory",
        [
            MaterialLibrary.S235,
            MaterialLibrary.S275,
            MaterialLibrary.S355,
            MaterialLibrary.S420,
            MaterialLibrary.S460,
        ],
    )
    def test_density(self, factory):
        assert factory().density == pytest.approx(7850)

    def test_yield_stress_ordering(self):
        """Higher grade must have higher yield stress."""
        grades = [
            MaterialLibrary.S235(),
            MaterialLibrary.S275(),
            MaterialLibrary.S355(),
            MaterialLibrary.S420(),
            MaterialLibrary.S460(),
        ]
        fy_values = [m.yield_stress for m in grades]
        assert fy_values == sorted(fy_values)


class TestAluminiumProperties:
    def test_e_mod_range(self):
        """All aluminium alloys: E typically 68–75 GPa."""
        for factory in [
            MaterialLibrary.aluminum_6061_T6,
            MaterialLibrary.aluminum_7075_T6,
            MaterialLibrary.aluminum_2024_T3,
            MaterialLibrary.aluminum_5083,
        ]:
            e = factory().e_mod
            assert 60e9 <= e <= 80e9, f"{factory()} E={e/1e9:.1f} GPa outside 60–80 GPa"

    def test_density_range(self):
        """Aluminium alloys: ρ typically 2600–2900 kg/m³."""
        for factory in [
            MaterialLibrary.aluminum_6061_T6,
            MaterialLibrary.aluminum_7075_T6,
            MaterialLibrary.aluminum_2024_T3,
            MaterialLibrary.aluminum_5083,
        ]:
            rho = factory().density
            assert 2600 <= rho <= 2900, f"{factory()} ρ={rho} outside 2600–2900"

    def test_7075_stronger_than_6061(self):
        assert (
            MaterialLibrary.aluminum_7075_T6().yield_stress > MaterialLibrary.aluminum_6061_T6().yield_stress
        )


class TestTitaniumProperties:
    def test_grade5_stronger_than_grade2(self):
        assert MaterialLibrary.titanium_grade5().yield_stress > MaterialLibrary.titanium_grade2().yield_stress

    def test_density_range(self):
        """Titanium alloys: ρ typically 4400–4550 kg/m³."""
        for factory in [MaterialLibrary.titanium_grade2, MaterialLibrary.titanium_grade5]:
            rho = factory().density
            assert 4400 <= rho <= 4600


class TestConcreteProperties:
    def test_characteristic_strength_ordering(self):
        """Higher concrete class must have higher fck (yield_stress)."""
        fck_values = [
            MaterialLibrary.concrete_C20_25().yield_stress,
            MaterialLibrary.concrete_C25_30().yield_stress,
            MaterialLibrary.concrete_C30_37().yield_stress,
            MaterialLibrary.concrete_C35_45().yield_stress,
        ]
        assert fck_values == sorted(fck_values)

    def test_e_mod_ordering(self):
        """Higher concrete class must have higher Ecm."""
        e_values = [
            MaterialLibrary.concrete_C20_25().e_mod,
            MaterialLibrary.concrete_C25_30().e_mod,
            MaterialLibrary.concrete_C30_37().e_mod,
            MaterialLibrary.concrete_C35_45().e_mod,
        ]
        assert e_values == sorted(e_values)

    def test_density_is_normal_weight(self):
        """All concrete grades defined here are normal-weight (ρ = 2400 kg/m³)."""
        for factory in [
            MaterialLibrary.concrete_C20_25,
            MaterialLibrary.concrete_C25_30,
            MaterialLibrary.concrete_C30_37,
            MaterialLibrary.concrete_C35_45,
        ]:
            assert factory().density == pytest.approx(2400)


# ---------------------------------------------------------------------------
# 4. Registry helpers
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_get_returns_correct_material(self):
        mat = MaterialLibrary.get("S355")
        assert mat.name == "S355"
        assert mat.yield_stress == pytest.approx(355e6)

    def test_get_aluminium_by_name(self):
        mat = MaterialLibrary.get("Aluminium 6061-T6")
        assert mat.e_mod == pytest.approx(68.9e9)

    def test_get_unknown_name_raises_key_error(self):
        with pytest.raises(KeyError, match="Unknown material"):
            MaterialLibrary.get("Unobtainium X42")

    def test_all_names_are_retrievable(self):
        """Every name returned by list_available() must resolve via get()."""
        for name in MaterialLibrary.list_available():
            mat = MaterialLibrary.get(name)
            assert mat.name == name

    def test_list_available_contains_expected_names(self):
        names = MaterialLibrary.list_available()
        for expected in [
            "S235",
            "S355",
            "S460",
            "Aluminium 6061-T6",
            "Titanium Grade 5 (Ti-6Al-4V)",
            "Concrete C25/30",
            "Stainless 1.4301 (304)",
            "Brass CuZn37",
        ]:
            assert expected in names, f"'{expected}' missing from list_available()"


# ---------------------------------------------------------------------------
# 5. Independence — each call must return a distinct object
# ---------------------------------------------------------------------------


class TestIndependence:
    def test_two_calls_return_different_objects(self):
        a = MaterialLibrary.S355()
        b = MaterialLibrary.S355()
        assert a is not b

    def test_two_calls_have_different_ids(self):
        a = MaterialLibrary.S355()
        b = MaterialLibrary.S355()
        assert a.id != b.id

    def test_mutation_does_not_affect_subsequent_call(self):
        a = MaterialLibrary.S355()
        a.yield_stress = 999e9  # mutate
        b = MaterialLibrary.S355()
        assert b.yield_stress == pytest.approx(355e6)
