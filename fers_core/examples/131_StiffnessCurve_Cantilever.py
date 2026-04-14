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
# Example 131: StiffnessCurve — Axial-Load Dependent Rotational Spring
# =============================================================================
#
# A 5 m vertical cantilever (HEB 200) with a semi-rigid base connection whose
# rotational stiffness increases with compressive axial load — modelling the
# behaviour of warehouse racking base plates that engage more as the upright
# carries heavier loads.
#
#   Axial Load [kN]   Rotational Stiffness [kNm/rad]
#   ─────────────────  ──────────────────────────────
#    0  – 20              2,500   (minimum — base plate barely engaged)
#   20  – 60              linear increase to 5,000
#   60  – 80              continues to 6,250 (fully engaged)
#
# Setup:
#   • 1 kN lateral load at the top  (global +X)
#   • 0 – 80 kN compressive load    (global −Z)
#   • 9 load cases, one per axial-load level
#
# Three results are compared:
#   (A)  StiffnessCurve   — nonlinear: stiffness re-evaluated each iteration
#   (B)  Constant Spring  — nonlinear: fixed at the curve minimum (2,500 kNm/rad)
#   (C)  Analytical 1st-order — closed-form δ = Fh²/k + Fh³/(3EI), no P-δ
#
# Reference data: Spring/ folder (StiffnessDiagram.png, FirstOrder.csv)
# =============================================================================


# ── Parameters ────────────────────────────────────────────────────────────────

H = 5.0  # column height [m]
F_H = 1000.0  # 1 kN lateral load [N]
AXIAL_LOADS_KN = [0, 10, 20, 30, 40, 50, 60, 70, 80]

# Stiffness curve  [axial_load (N), rotational_stiffness (Nm/rad)]
# Symmetric: same curve for tension and compression
STIFFNESS_CURVE = [
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

K_CONST = 2_500_000  # constant spring for comparison [Nm/rad]


# ── Material & Section ───────────────────────────────────────────────────────

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
    i_y=2.003e-5,  # weak-axis I  [m⁴]
    i_z=5.696e-5,  # strong-axis I [m⁴] — resists bending in XZ plane
    j=5.92e-7,  # torsion constant [m⁴]
    area=7.81e-3,  # area [m²]
)

EI = steel.e_mod * heb200.i_z  # flexural stiffness for analytical formula


# ── Helper: build cantilever model ───────────────────────────────────────────


def build_model(ry_condition):
    """
    Vertical cantilever with the given Ry support condition at the base.
    All other DOFs are fixed (default).  Returns (model, base_node, top_node).
    """
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

    support = NodalSupport(rotation_conditions={"Y": ry_condition})
    base.nodal_support = support

    column = Member(start_node=base, end_node=top, section=heb200)
    model.add_member_set(MemberSet(members=[column]))

    for n_kn in AXIAL_LOADS_KN:
        lc = model.create_load_case(name=f"N={n_kn}kN")
        NodalLoad(node=top, load_case=lc, magnitude=F_H, direction=(1, 0, 0))
        if n_kn > 0:
            NodalLoad(
                node=top,
                load_case=lc,
                magnitude=n_kn * 1000,
                direction=(0, 0, -1),
            )

    return model, base, top


# ── Analytical first-order deflection ─────────────────────────────────────────


def interpolate_k(n_kn):
    """Linearly interpolate rotational stiffness from the curve."""
    fz = n_kn * 1000  # kN → N
    curve = STIFFNESS_CURVE
    if fz <= curve[0][0]:
        return curve[0][1]
    if fz >= curve[-1][0]:
        return curve[-1][1]
    for i in range(len(curve) - 1):
        if curve[i][0] <= fz <= curve[i + 1][0]:
            t = (fz - curve[i][0]) / (curve[i + 1][0] - curve[i][0])
            return curve[i][1] + t * (curve[i + 1][1] - curve[i][1])
    return curve[-1][1]


def analytical_first_order_mm(n_kn):
    """δ = Fh²/k + Fh³/(3EI)  — first-order, no P-δ  [mm]."""
    k = interpolate_k(n_kn)
    delta_spring = F_H * H**2 / k
    delta_beam = F_H * H**3 / (3 * EI)
    return (delta_spring + delta_beam) * 1000  # m → mm


# ── Run models ────────────────────────────────────────────────────────────────

print("=" * 78)
print("  Example 131: StiffnessCurve — Axial-Load Dependent Rotational Spring")
print("=" * 78)
print(f"\n  Column :  HEB 200,  h = {H} m,  Steel S235")
print(f"  Lateral:  {F_H / 1000:.0f} kN  in X-direction at top")
print(
    f"  Spring :  Ry = spring_curve(Vz)"
    f"  ({STIFFNESS_CURVE[4][1] / 1e6:.1f}"
    f" – {STIFFNESS_CURVE[-1][1] / 1e6:.2f} MNm/rad)"
)
print()

# (A) Load-dependent rotational spring
print("  ► Solving Model A (spring_curve)…")
model_a, base_a, top_a = build_model(SupportCondition.spring_curve(ForceComponent.Vz, STIFFNESS_CURVE))
file_path = os.path.join("json_input_solver", "131_StiffnessCurve_Cantilever.json")
os.makedirs(os.path.dirname(file_path), exist_ok=True)
model_a.save_to_json(file_path, indent=4)
model_a.run_analysis()

# (B) Constant spring at curve minimum
print("  ► Solving Model B (constant spring)…")
model_b, base_b, top_b = build_model(SupportCondition.spring(K_CONST))
model_b.run_analysis()


# ── Results table ─────────────────────────────────────────────────────────────

print()
print("─" * 78)
print(
    f"  {'Axial':>6}  │ {'k(N)':>10}  │"
    f" {'(A) Curve':>10}  │ {'(B) Const':>10}  │"
    f" {'(C) Analyt.':>12}  │ {'A vs C':>7}"
)
print(
    f"  {'[kN]':>6}  │ {'[kNm/rad]':>10}  │"
    f" {'dx [mm]':>10}  │ {'dx [mm]':>10}  │"
    f" {'dx [mm]':>12}  │ {'[%]':>7}"
)
print("─" * 78)

for n_kn in AXIAL_LOADS_KN:
    lc_name = f"N={n_kn}kN"
    k_interp = interpolate_k(n_kn)

    ra = model_a.resultsbundle.loadcases[lc_name]
    dx_a = ra.displacement_nodes[str(top_a.id)].dx * 1000

    rb = model_b.resultsbundle.loadcases[lc_name]
    dx_b = rb.displacement_nodes[str(top_b.id)].dx * 1000

    dx_c = analytical_first_order_mm(n_kn)

    pct = ((dx_a - dx_c) / dx_c * 100) if dx_c != 0 else 0.0

    print(
        f"  {n_kn:>6}  │ {k_interp / 1000:>10,.0f}  │"
        f" {dx_a:>10.2f}  │ {dx_b:>10.2f}  │"
        f" {dx_c:>12.2f}  │ {pct:>+6.1f}%"
    )

print("─" * 78)

print(
    """
  Observations
  ────────────
  (A) StiffnessCurve:  stiffness increases with axial load → deflection
      decreases.  A small P-δ amplification partially offsets the gain.

  (B) Constant Spring:  stiffness stays at 2,500 kNm/rad → deflection grows
      monotonically as P-δ (N·δ effect) amplifies the lateral displacement.

  (C) Analytical 1st-order:  δ = Fh²/k + Fh³/(3EI) using the interpolated k.
      No P-δ.  Matches (A) at zero axial load; diverges as axial load grows.

  This demonstrates how racking base plates that stiffen under compression
  can reduce sway — an effect that a constant spring model cannot capture.
"""
)
