"""
121 — Shear Deformation Toggle (Euler-Bernoulli vs Timoshenko)
==============================================================

Demonstrates how to toggle shear deformation on and off for a cantilever beam.
Compares:
  • Euler-Bernoulli (no shear deformation)  →  δ = PL³ / (3EI)
  • Timoshenko     (with shear deformation)  →  δ = PL³ / (3EI)  +  PL / (GA_s)

Using a short/stocky IPE300 beam (L/h ≈ 6.7) the shear contribution is clearly
visible.  For slender beams (L/h > 20) the difference becomes negligible.

Cross-check:  RFEM "Shear Deformation" tickbox in Calculation Parameters → same
              toggle as `include_shear_deformation` in FERS AnalysisOptions.
"""

from fers_core import (
    Node,
    Member,
    FERS,
    Material,
    Section,
    MemberSet,
    NodalSupport,
    NodalLoad,
)
from fers_core.settings.settings import Settings
from fers_core.settings.anlysis_options import AnalysisOptions


# =============================================================================
# Parameters
# =============================================================================
L = 1.0  # Beam length [m]  — short beam so shear matters
P = 100_000.0  # End load [N] (10 kN, downward → negative Y)

# Material: Steel S355
steel = Material(name="S355", e_mod=210e9, g_mod=81e9, density=7850, yield_stress=355e6)

# Section: IPE300 from built-in library (includes shear areas a_sy, a_sz)
ipe300 = Section.from_name("IPE300", steel)

# Print section properties for reference
print("=" * 72)
print("Section: IPE300")
print(f"  A      = {ipe300.area * 1e4:.2f} cm²")
print(f"  I_y    = {ipe300.i_y * 1e8:.2f} cm⁴")
print(f"  I_z    = {ipe300.i_z * 1e8:.2f} cm⁴")
print(f"  J      = {ipe300.j * 1e8:.4f} cm⁴")
print(f"  I_w    = {ipe300.i_w * 1e12:.2f} cm⁶" if ipe300.i_w else "  I_w    = not computed")
print(f"  A_sy   = {ipe300.a_sy * 1e4:.2f} cm²" if ipe300.a_sy else "  A_sy   = not computed")
print(f"  A_sz   = {ipe300.a_sz * 1e4:.2f} cm²" if ipe300.a_sz else "  A_sz   = not computed")
print("=" * 72)


def run_cantilever(include_shear: bool, label: str):
    """Build and analyse a cantilever, return tip deflection dy."""
    options = AnalysisOptions(include_shear_deformation=include_shear)
    settings = Settings(analysis_options=options)
    model = FERS(settings=settings)

    n1 = Node(0, 0, 0)
    n2 = Node(L, 0, 0)

    n1.nodal_support = NodalSupport()  # fully fixed

    beam = Member(start_node=n1, end_node=n2, section=ipe300)
    model.add_member_set(MemberSet(members=[beam]))

    lc = model.create_load_case(name="Tip load")
    NodalLoad(node=n2, load_case=lc, magnitude=-P, direction=(0, 1, 0))

    print(f"\nRunning analysis: {label} ...")
    model.run_analysis()

    dy = model.resultsbundle.loadcases["Tip load"].displacement_nodes["2"].dy
    return dy


# =============================================================================
# Run with and without shear deformation
# =============================================================================
dy_eb = run_cantilever(include_shear=False, label="Euler-Bernoulli (no shear)")
dy_timo = run_cantilever(include_shear=True, label="Timoshenko (with shear)")


# =============================================================================
# Analytical reference values
# =============================================================================
E = steel.e_mod
G = steel.g_mod
I_z = ipe300.i_z  # bending about z-axis for load in Y
A_sz = ipe300.a_sz  # shear area for shear in Y-direction

delta_eb_analytical = -P * L**3 / (3 * E * I_z)
delta_shear = -P * L / (G * A_sz) if A_sz else 0.0
delta_timo_analytical = delta_eb_analytical + delta_shear


# =============================================================================
# Results comparison
# =============================================================================
print("\n" + "=" * 72)
print("RESULTS: Cantilever IPE300, L = {:.1f} m, P = {:.0f} kN".format(L, P / 1000))
print("=" * 72)

print(f"\n{'':30s} {'FERS':>14s} {'Analytical':>14s} {'Diff':>10s}")
print("-" * 72)

print(
    f"{'Euler-Bernoulli δ_y [mm]':30s} {dy_eb*1e3:14.4f} {delta_eb_analytical*1e3:14.4f} "
    f"{abs(dy_eb - delta_eb_analytical)*1e3:10.6f}"
)

print(
    f"{'Timoshenko δ_y [mm]':30s} {dy_timo*1e3:14.4f} {delta_timo_analytical*1e3:14.4f} "
    f"{abs(dy_timo - delta_timo_analytical)*1e3:10.6f}"
)

shear_pct = (abs(dy_timo) - abs(dy_eb)) / abs(dy_eb) * 100 if dy_eb != 0 else 0
shear_analytical_pct = abs(delta_shear) / abs(delta_eb_analytical) * 100 if delta_eb_analytical != 0 else 0

print(f"\nShear contribution:  FERS = {shear_pct:.2f}%    Analytical = {shear_analytical_pct:.2f}%")
print(f"  (PL/(GA_s) = {abs(delta_shear)*1e3:.4f} mm)")

print("\n--- Validation ---")
tol_eb = 1e-6
tol_timo = 1e-4  # FE vs analytical for shear might differ slightly for section props
if abs(dy_eb - delta_eb_analytical) < tol_eb:
    print("Euler-Bernoulli deflection matches analytical ✅")
else:
    print("Euler-Bernoulli deflection does NOT match analytical ❌")

if abs(dy_timo - delta_timo_analytical) / abs(delta_timo_analytical) < 0.01:
    print("Timoshenko deflection within 1% of analytical   ✅")
else:
    print(
        f"Timoshenko deflection differs by "
        f"{abs(dy_timo - delta_timo_analytical)/abs(delta_timo_analytical)*100:.2f}% ❌"
    )
