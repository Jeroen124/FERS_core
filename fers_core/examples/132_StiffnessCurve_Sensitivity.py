import os
from fers_core import (
    Node,
    Member,
    FERS,
    Material,
    Section,
    MemberSet,
    NodalSupport,
    NodalLoad,
    SupportCondition,
    ForceComponent,
)
from fers_core.settings.settings import Settings
from fers_core.settings.anlysis_options import AnalysisOptions
from fers_core.settings.enums import AnalysisOrder


# =============================================================================
# Example 132: StiffnessCurve — Deflection Sensitivity to Axial Load
# =============================================================================
#
# Eight independent cantilevers, each with the same 1 kN lateral load but a
# different compressive axial load (10 – 80 kN).  The base rotation spring
# stiffness depends on the axial reaction via a StiffnessCurve.
#
# This example builds individual models per axial-load level so that the
# JSON output for each is self-contained and easy to inspect.
# =============================================================================


# ── Parameters ────────────────────────────────────────────────────────────────

H = 5.0  # column height [m]
F_LATERAL = 1000.0  # 1 kN lateral force [N]

# Stiffness curve [axial_load (N), rotational_stiffness (Nm/rad)]
CURVE = [
    [-80_000, 6_250_000],
    [-60_000, 5_000_000],
    [-40_000, 3_750_000],
    [-20_000, 2_500_000],
    [0, 2_500_000],
    [20_000, 2_500_000],
    [40_000, 3_750_000],
    [60_000, 5_000_000],
    [80_000, 6_250_000],
]

# Material & section (same as Example 131)
steel = Material(
    name="Steel S235",
    e_mod=210e9,
    g_mod=80.769e9,
    density=7850,
    yield_stress=235e6,
)

heb200 = Section(
    name="HEB 200",
    material=steel,
    i_y=2.003e-5,
    i_z=5.696e-5,
    j=5.92e-7,
    area=7.81e-3,
)


# ── Solve one cantilever per axial-load level ─────────────────────────────────

print("=" * 60)
print("  Example 132: Deflection Sensitivity to Axial Load")
print("=" * 60)
print(f"\n  Column:   HEB 200,  h = {H} m")
print(f"  Lateral:  {F_LATERAL / 1000:.0f} kN (constant for all models)")
print("  Support:  Ry = spring_curve(Vz) (2,500 – 6,250 kNm/rad)\n")

results = []

for n_kn in range(10, 90, 10):
    Node.reset_counter()
    NodalSupport.reset_counter()

    model = FERS(
        settings=Settings(
            analysis_options=AnalysisOptions(
                order=AnalysisOrder.NONLINEAR,
                tolerance=0.001,
                max_iterations=50,
            )
        )
    )

    base = Node(0, 0, 0)
    top = Node(0, 0, H)

    # Stiffness-curve support at the base (only Ry is semi-rigid)
    support = NodalSupport(rotation_conditions={"Y": SupportCondition.spring_curve(ForceComponent.Vz, CURVE)})
    base.nodal_support = support

    column = Member(start_node=base, end_node=top, section=heb200)
    model.add_member_set(MemberSet(members=[column]))

    lc = model.create_load_case(name="LC1")
    NodalLoad(node=top, load_case=lc, magnitude=F_LATERAL, direction=(1, 0, 0))
    NodalLoad(node=top, load_case=lc, magnitude=n_kn * 1000, direction=(0, 0, -1))

    # Save JSON for inspection
    out_dir = os.path.join("json_input_solver", "132_sensitivity")
    os.makedirs(out_dir, exist_ok=True)
    model.save_to_json(os.path.join(out_dir, f"cantilever_N{n_kn}kN.json"), indent=4)

    print(f"  Solving N = {n_kn:>2} kN …", end="  ")
    model.run_analysis()

    r = model.resultsbundle.loadcases["LC1"]
    dx = r.displacement_nodes[str(top.id)].dx * 1000  # mm
    ry = r.displacement_nodes[str(base.id)].ry * 1000  # mrad
    fz = r.reaction_nodes[str(base.id)].nodal_forces.fz / 1000  # kN

    results.append((n_kn, dx, ry, fz))
    print(f"dx = {dx:>7.2f} mm")


# ── Summary table ─────────────────────────────────────────────────────────────

print("\n" + "─" * 60)
print(f"  {'N [kN]':>8}  │ {'dx [mm]':>10}  │" f" {'φy [mrad]':>10}  │ {'Fz [kN]':>10}")
print("─" * 60)
for n_kn, dx, ry, fz in results:
    print(f"  {n_kn:>8}  │ {dx:>10.2f}  │" f" {ry:>10.3f}  │ {fz:>10.1f}")
print("─" * 60)

print(
    """
  As compressive load increases:
    • 10 – 20 kN:  spring at minimum stiffness → largest lateral deflection
    • 20 – 60 kN:  spring stiffens with axial load → deflection drops
    • 60 – 80 kN:  spring near maximum, but P-δ grows → deflection may plateau

  reference values (geometry and section differ, but the trend matches).
"""
)
