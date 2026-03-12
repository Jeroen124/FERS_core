"""
804 — Section Property Comparison
==================================
Demonstrates how to iterate over the section library to compare
properties across an entire series — useful for preliminary design
and optimisation.

Key features shown:
  • Section.list_available(series) to enumerate a family
  • Section.from_name() in a loop
  • Tabular output of A, I_y, I_z, J
  • Optional: finding the lightest section that satisfies a stiffness criterion
"""

from fers_core import Material, Section


# =============================================================================
# Step 1: Material
# =============================================================================
steel = Material(name="S355", e_mod=210e9, g_mod=81e9, density=7850, yield_stress=355e6)


# =============================================================================
# Step 2: Compare all IPE sections
# =============================================================================
print("=" * 90)
print(f"{'IPE Series':^90s}")
print("=" * 90)
print(
    f"{'Name':<12s}  {'h (mm)':>8s}  {'b (mm)':>8s}  {'A (cm²)':>10s}  "
    f"{'I_y (cm⁴)':>12s}  {'I_z (cm⁴)':>12s}  {'J (cm⁴)':>10s}"
)
print("-" * 90)

for name in Section.list_available("IPE"):
    sec = Section.from_name(name, steel)
    print(
        f"{sec.name:<12s}  {sec.h*1e3:8.1f}  {sec.b*1e3:8.1f}  "
        f"{sec.area*1e4:10.2f}  {sec.i_y*1e8:12.2f}  "
        f"{sec.i_z*1e8:12.2f}  {sec.j*1e8:10.4f}"
    )


# =============================================================================
# Step 3: Find the lightest IPE that satisfies a deflection limit
# =============================================================================
# Problem: cantilever L = 5 m, tip load F = 10 kN, max deflection L/300
L = 5.0  # m
F = 10_000.0  # N
E = 210e9  # Pa
delta_max = L / 300  # allowable deflection (m)

# For a cantilever: delta = F·L³ / (3·E·I)  →  I_min = F·L³ / (3·E·delta_max)
I_min = F * L**3 / (3 * E * delta_max)

print(
    f"\n--- Lightest IPE for cantilever {L:.0f} m, F = {F/1e3:.0f} kN, "
    f"δ_max = L/300 = {delta_max*1e3:.2f} mm ---"
)
print(f"    Required I_z ≥ {I_min*1e8:.2f} cm⁴\n")

found = None
for name in Section.list_available("IPE"):
    sec = Section.from_name(name, steel)
    if sec.i_z >= I_min:
        found = sec
        break

if found:
    delta = F * L**3 / (3 * E * found.i_z)
    print(
        f"  ✓ {found.name}  I_z = {found.i_z*1e8:.2f} cm⁴  "
        f"δ = {delta*1e3:.2f} mm  (limit = {delta_max*1e3:.2f} mm)"
    )
else:
    print("  ✗ No IPE section is large enough — consider HEB or a welded section.")


# =============================================================================
# Step 4: Compare HEA vs HEB vs HEM at the same nominal height
# =============================================================================
print("\n" + "=" * 90)
print(f"{'HE-series comparison at h ≈ 300 mm':^90s}")
print("=" * 90)
print(
    f"{'Name':<12s}  {'h (mm)':>8s}  {'b (mm)':>8s}  {'A (cm²)':>10s}  "
    f"{'I_z (cm⁴)':>12s}  {'weight (kg/m)':>14s}"
)
print("-" * 90)

for series_name in ["HEA300", "HEB300", "HEM300"]:
    sec = Section.from_name(series_name, steel)
    weight_per_m = sec.area * steel.density  # kg/m
    print(
        f"{sec.name:<12s}  {sec.h*1e3:8.1f}  {sec.b*1e3:8.1f}  "
        f"{sec.area*1e4:10.2f}  {sec.i_z*1e8:12.2f}  {weight_per_m:14.2f}"
    )
