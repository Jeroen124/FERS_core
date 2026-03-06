"""
Default Material Library
========================
Ready-to-use factory methods for common structural engineering materials.

Each method returns a **new** :class:`~fers_core.members.material.Material`
instance so that multiple models can each own their own copy without
sharing IDs or state.

Usage::

    from fers_core import MaterialLibrary

    steel  = MaterialLibrary.S355()
    alu    = MaterialLibrary.aluminum_6061_T6()
    titan  = MaterialLibrary.titanium_grade5()

    print(MaterialLibrary.list_available())
    mat = MaterialLibrary.get("S355")

Sources
-------
* Steel (EN 10025 / EN 1993-1-1): E = 210 GPa, G = 81 GPa
* Stainless steel (EN 10088 / EN 1993-1-4): E = 200 GPa, G = 77 GPa
* Aluminium (EN 1999-1-1 / Matweb): various alloys
* Titanium (AMS / ASTM): Grade 2 and Grade 5 (Ti-6Al-4V)
* Copper / Brass (ISO 1336 / Matweb)
* Concrete (EN 1992-1-1 / EN 206): Ecm secant modulus, G = Ecm / 2.4
* Cast iron (EN 1563 / EN 1561)
"""

from __future__ import annotations

from typing import Callable, Dict, List

from .material import Material


class MaterialLibrary:
    """
    Collection of pre-defined engineering materials.

    Every class method creates and returns a fresh :class:`.Material` object.
    Call :meth:`list_available` to see all registered names, and
    :meth:`get` to look one up by name string.
    """

    # ------------------------------------------------------------------
    # Structural steel — EN 10025 / EN 1993-1-1
    # E = 210 GPa, G = 81 GPa, rho = 7850 kg/m³
    # ------------------------------------------------------------------

    @staticmethod
    def S235() -> Material:
        """Structural steel S235 (EN 10025-2)."""
        return Material("S235", e_mod=210e9, g_mod=81e9, density=7850, yield_stress=235e6)

    @staticmethod
    def S275() -> Material:
        """Structural steel S275 (EN 10025-2)."""
        return Material("S275", e_mod=210e9, g_mod=81e9, density=7850, yield_stress=275e6)

    @staticmethod
    def S355() -> Material:
        """Structural steel S355 (EN 10025-2)."""
        return Material("S355", e_mod=210e9, g_mod=81e9, density=7850, yield_stress=355e6)

    @staticmethod
    def S420() -> Material:
        """High-strength structural steel S420 (EN 10025-3/4)."""
        return Material("S420", e_mod=210e9, g_mod=81e9, density=7850, yield_stress=420e6)

    @staticmethod
    def S460() -> Material:
        """High-strength structural steel S460 (EN 10025-3/4)."""
        return Material("S460", e_mod=210e9, g_mod=81e9, density=7850, yield_stress=460e6)

    # ------------------------------------------------------------------
    # Stainless steel — EN 10088 / EN 1993-1-4
    # E = 200 GPa, G = 77 GPa
    # ------------------------------------------------------------------

    @staticmethod
    def stainless_304() -> Material:
        """Austenitic stainless steel 1.4301 / AISI 304 (EN 10088-1).
        0.2% proof stress (Rp0.2) used as yield_stress."""
        return Material("Stainless 1.4301 (304)", e_mod=200e9, g_mod=77e9, density=7900, yield_stress=210e6)

    @staticmethod
    def stainless_316() -> Material:
        """Austenitic stainless steel 1.4401 / AISI 316 (EN 10088-1).
        0.2% proof stress (Rp0.2) used as yield_stress."""
        return Material("Stainless 1.4401 (316)", e_mod=200e9, g_mod=77e9, density=8000, yield_stress=220e6)

    # ------------------------------------------------------------------
    # Aluminium alloys — EN 1999-1-1
    # ------------------------------------------------------------------

    @staticmethod
    def aluminum_6061_T6() -> Material:
        """Aluminium alloy 6061-T6 (EN AW-6061 / AA 6061).
        General-purpose structural alloy, good weldability."""
        return Material("Aluminium 6061-T6", e_mod=68.9e9, g_mod=26.0e9, density=2700, yield_stress=276e6)

    @staticmethod
    def aluminum_7075_T6() -> Material:
        """Aluminium alloy 7075-T6 (EN AW-7075 / AA 7075).
        High-strength aerospace alloy."""
        return Material("Aluminium 7075-T6", e_mod=71.7e9, g_mod=26.9e9, density=2810, yield_stress=503e6)

    @staticmethod
    def aluminum_2024_T3() -> Material:
        """Aluminium alloy 2024-T3 (EN AW-2024 / AA 2024).
        Excellent fatigue resistance, aerospace applications."""
        return Material("Aluminium 2024-T3", e_mod=73.1e9, g_mod=28.0e9, density=2780, yield_stress=345e6)

    @staticmethod
    def aluminum_5083() -> Material:
        """Aluminium alloy 5083-H111 (EN AW-5083).
        Marine / cryogenic applications, excellent corrosion resistance."""
        return Material("Aluminium 5083-H111", e_mod=70.3e9, g_mod=26.4e9, density=2660, yield_stress=145e6)

    # ------------------------------------------------------------------
    # Titanium — ASTM / AMS
    # ------------------------------------------------------------------

    @staticmethod
    def titanium_grade2() -> Material:
        """Titanium Grade 2 – commercially pure (ASTM B265).
        Excellent corrosion resistance, moderate strength."""
        return Material("Titanium Grade 2 (CP)", e_mod=105e9, g_mod=40e9, density=4510, yield_stress=275e6)

    @staticmethod
    def titanium_grade5() -> Material:
        """Titanium Grade 5 – Ti-6Al-4V (ASTM B265 / AMS 4928).
        Highest strength-to-weight ratio; aerospace standard."""
        return Material(
            "Titanium Grade 5 (Ti-6Al-4V)", e_mod=114e9, g_mod=44e9, density=4430, yield_stress=880e6
        )

    # ------------------------------------------------------------------
    # Copper and copper alloys
    # ------------------------------------------------------------------

    @staticmethod
    def copper() -> Material:
        """Pure copper C11000 (electrolytic tough pitch), annealed.
        High electrical / thermal conductivity."""
        return Material("Copper C11000 (annealed)", e_mod=117e9, g_mod=44e9, density=8960, yield_stress=70e6)

    @staticmethod
    def brass() -> Material:
        """Brass CuZn37 / C27200 (cartridge brass, 63/37).
        Good machinability and moderate strength."""
        return Material("Brass CuZn37", e_mod=100e9, g_mod=37e9, density=8440, yield_stress=180e6)

    @staticmethod
    def bronze() -> Material:
        """Tin bronze CuSn8 / C52100.
        Good wear resistance and bearing properties."""
        return Material("Bronze CuSn8", e_mod=105e9, g_mod=40e9, density=8800, yield_stress=320e6)

    # ------------------------------------------------------------------
    # Concrete — EN 1992-1-1 / EN 206
    # Ecm (secant modulus) computed from Ecm = 22000·(fcm/10)^0.3 [MPa]
    # Poisson's ratio ν ≈ 0.20  →  G = Ecm / 2.4
    # yield_stress = fck (characteristic cylinder compressive strength)
    # ------------------------------------------------------------------

    @staticmethod
    def concrete_C20_25() -> Material:
        """Normal-weight concrete C20/25 (EN 206).
        Ecm = 30 GPa, fck = 20 MPa (cylinder)."""
        return Material("Concrete C20/25", e_mod=30.0e9, g_mod=12.5e9, density=2400, yield_stress=20e6)

    @staticmethod
    def concrete_C25_30() -> Material:
        """Normal-weight concrete C25/30 (EN 206).
        Ecm = 31 GPa, fck = 25 MPa (cylinder)."""
        return Material("Concrete C25/30", e_mod=31.0e9, g_mod=12.9e9, density=2400, yield_stress=25e6)

    @staticmethod
    def concrete_C30_37() -> Material:
        """Normal-weight concrete C30/37 (EN 206).
        Ecm = 33 GPa, fck = 30 MPa (cylinder)."""
        return Material("Concrete C30/37", e_mod=33.0e9, g_mod=13.8e9, density=2400, yield_stress=30e6)

    @staticmethod
    def concrete_C35_45() -> Material:
        """Normal-weight concrete C35/45 (EN 206).
        Ecm = 34 GPa, fck = 35 MPa (cylinder)."""
        return Material("Concrete C35/45", e_mod=34.0e9, g_mod=14.2e9, density=2400, yield_stress=35e6)

    # ------------------------------------------------------------------
    # Cast iron — EN 1561 / EN 1563
    # ------------------------------------------------------------------

    @staticmethod
    def cast_iron_grey() -> Material:
        """Grey cast iron GJL-250 (EN 1561 / ISO 185).
        Brittle; yield_stress represents minimum tensile strength."""
        return Material("Grey Cast Iron GJL-250", e_mod=120e9, g_mod=46e9, density=7200, yield_stress=250e6)

    @staticmethod
    def cast_iron_ductile() -> Material:
        """Ductile (nodular) cast iron GJS-400-18 (EN 1563 / ISO 1083).
        yield_stress = 0.2% proof stress (Rp0.2)."""
        return Material(
            "Ductile Cast Iron GJS-400-18", e_mod=169e9, g_mod=65e9, density=7100, yield_stress=250e6
        )

    # ------------------------------------------------------------------
    # Registry helpers
    # ------------------------------------------------------------------

    #: Internal map: display name → factory callable.
    #: Populated at class-definition time; order reflects grouping above.
    _REGISTRY: Dict[str, Callable[[], Material]] = {}

    @classmethod
    def list_available(cls) -> List[str]:
        """Return a sorted list of all registered material names."""
        return sorted(cls._REGISTRY.keys())

    @classmethod
    def get(cls, name: str) -> Material:
        """
        Return a new :class:`.Material` instance by display name.

        Parameters
        ----------
        name : str
            Case-sensitive display name as shown by :meth:`list_available`.

        Raises
        ------
        KeyError
            If *name* is not found in the registry.
        """
        try:
            return cls._REGISTRY[name]()
        except KeyError:
            available = ", ".join(cls.list_available())
            raise KeyError(f"Unknown material '{name}'. Available: {available}") from None


# ---------------------------------------------------------------------------
# Build the registry automatically from all public static methods
# that return a Material (i.e. every factory defined above).
# ---------------------------------------------------------------------------
def _build_registry() -> None:
    for _attr_name in dir(MaterialLibrary):
        if _attr_name.startswith("_"):
            continue
        _obj = getattr(MaterialLibrary, _attr_name)
        if not callable(_obj):
            continue
        # Call it, check the return type
        try:
            _sample = _obj()
        except TypeError:
            continue
        if isinstance(_sample, Material):
            MaterialLibrary._REGISTRY[_sample.name] = _obj


_build_registry()
