"""
808 — Default Material Library
================================
Demonstrates the built-in ``MaterialLibrary`` and how to use its
pre-defined materials directly in a FERS model.

Materials covered:
  • Structural steel        — S235, S275, S355, S420, S460
  • Stainless steel         — 1.4301 (304), 1.4401 (316)
  • Aluminium alloys        — 6061-T6, 7075-T6, 2024-T3, 5083-H111
  • Titanium                — Grade 2 (CP), Grade 5 (Ti-6Al-4V)
  • Copper / brass / bronze — C11000, CuZn37, CuSn8
  • Concrete                — C20/25, C25/30, C30/37, C35/45
  • Cast iron               — GJL-250, GJS-400-18

All SI units (Pa, kg/m³).
"""

from fers_core import (
    MaterialLibrary,
)


# =============================================================================
# Step 1: List every registered material
# =============================================================================
print("Available materials in MaterialLibrary:")
print("-" * 44)
for name in MaterialLibrary.list_available():
    print(f"  {name}")


# =============================================================================
# Step 2: Print a comparison table
# =============================================================================
groups = {
    "Structural steel": [
        MaterialLibrary.S235,
        MaterialLibrary.S275,
        MaterialLibrary.S355,
        MaterialLibrary.S420,
        MaterialLibrary.S460,
    ],
    "Stainless steel": [
        MaterialLibrary.stainless_304,
        MaterialLibrary.stainless_316,
    ],
    "Aluminium": [
        MaterialLibrary.aluminum_6061_T6,
        MaterialLibrary.aluminum_7075_T6,
        MaterialLibrary.aluminum_2024_T3,
        MaterialLibrary.aluminum_5083,
    ],
    "Titanium": [
        MaterialLibrary.titanium_grade2,
        MaterialLibrary.titanium_grade5,
    ],
    "Copper / brass / bronze": [
        MaterialLibrary.copper,
        MaterialLibrary.brass,
        MaterialLibrary.bronze,
    ],
    "Concrete": [
        MaterialLibrary.concrete_C20_25,
        MaterialLibrary.concrete_C25_30,
        MaterialLibrary.concrete_C30_37,
        MaterialLibrary.concrete_C35_45,
    ],
    "Cast iron": [
        MaterialLibrary.cast_iron_grey,
        MaterialLibrary.cast_iron_ductile,
    ],
}

HDR = f"\n{'Material':<35s}  {'E (GPa)':>9s}  {'G (GPa)':>9s}  {'ρ (kg/m³)':>10s}  {'fy (MPa)':>9s}"
SEP = "-" * 80

for group_name, factories in groups.items():
    print(f"\n{group_name}")
    print(HDR)
    print(SEP)
    for factory in factories:
        mat = factory()
        print(
            f"  {mat.name:<33s}  {mat.e_mod/1e9:9.1f}  {mat.g_mod/1e9:9.1f}"
            f"  {mat.density:10.0f}  {mat.yield_stress/1e6:9.1f}"
        )


# =============================================================================
# Step 3: Look up a material by name (useful when reading from config / JSON)
# =============================================================================
mat_by_name = MaterialLibrary.get("Aluminium 6061-T6")
print(f"\nLooked up by name: '{mat_by_name.name}'  E = {mat_by_name.e_mod/1e9:.1f} GPa")


# =============================================================================
# Step 4: Compare tip deflection of a cantilever across materials
#
#  Same IPE200 section geometry, same 5 kN end load, L = 4 m.
#  Only the material (Young's modulus) changes.
# =============================================================================
print("\n--- Cantilever tip deflection — IPE200, L=4 m, F=5 kN ---")
print(f"{'Material':<35s}  {'E (GPa)':>9s}  {'δ (mm)':>9s}")
print("-" * 60)

comparison_materials = [
    MaterialLibrary.S355,
    MaterialLibrary.stainless_304,
    MaterialLibrary.aluminum_6061_T6,
    MaterialLibrary.aluminum_7075_T6,
    MaterialLibrary.titanium_grade5,
]

L = 4.0  # m
F = 5_000.0  # N
# IPE200: Iy = 1943 cm⁴ → 1943e-8 m⁴
I_y = 1943e-8  # m⁴

for factory in comparison_materials:
    mat = factory()

    # Analytical cantilever tip deflection: δ = F·L³ / (3·E·I)
    delta = F * L**3 / (3 * mat.e_mod * I_y)

    print(f"  {mat.name:<33s}  {mat.e_mod/1e9:9.1f}  {delta*1e3:9.3f}")
