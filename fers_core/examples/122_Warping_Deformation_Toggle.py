"""
122 — Warping Deformation Toggle (St. Venant vs Vlasov Torsion)
================================================================

Demonstrates how to toggle warping on and off for a cantilever beam
subjected to an end torque.

Compares:
  • St. Venant only  (include_warping=False) →  θ = T·L / (G·J)
  • Vlasov warping   (include_warping=True)  →  θ = (T·L/GJ)·[1 − tanh(kL)/(kL)]
    where k = √(G·J / E·I_w)

For open thin-walled sections (I-beams, channels) with restrained warping at the
support, the Vlasov theory predicts LESS twist than pure St. Venant because the
flanges resist warping through differential bending.

Cross-check: RFEM "7 Degrees of Freedom" / warping analysis module.
"""

import math
from fers_core import (
    Node,
    Member,
    FERS,
    Material,
    Section,
    MemberSet,
    NodalSupport,
    NodalMoment,
    SupportCondition,
)
from fers_core.settings.settings import Settings
from fers_core.settings.anlysis_options import AnalysisOptions


# =============================================================================
# Parameters
# =============================================================================
L = 3.0  # Beam length [m]
T = 1_000.0  # End torque [N·m] (1 kN·m about X-axis)

# Material: Steel S355
steel = Material(name="S355", e_mod=210e9, g_mod=81e9, density=7850, yield_stress=355e6)

# Section: IPE300 from built-in library (includes warping constant I_w)
ipe300 = Section.from_name("IPE300", steel)

# Print section properties
print("=" * 72)
print("Section: IPE300")
print(f"  J      = {ipe300.j * 1e8:.4f} cm⁴")
print(f"  I_w    = {ipe300.i_w * 1e12:.2f} cm⁶" if ipe300.i_w else "  I_w    = not computed")
print(f"  A_sy   = {ipe300.a_sy * 1e4:.2f} cm²" if ipe300.a_sy else "  A_sy   = not computed")
print(f"  A_sz   = {ipe300.a_sz * 1e4:.2f} cm²" if ipe300.a_sz else "  A_sz   = not computed")
print("=" * 72)


def run_torsion_cantilever(include_warping: bool, label: str, n_elements: int = 10):
    """
    Build a cantilever with end torque and return tip twist θ_x.

    Uses multiple elements for Vlasov convergence.
    Fixed end has warping restrained (θ' = 0).
    """
    options = AnalysisOptions(include_warping=include_warping)
    settings = Settings(analysis_options=options)
    model = FERS(settings=settings)

    # Create nodes along the beam
    nodes = [Node(i * L / n_elements, 0, 0) for i in range(n_elements + 1)]

    # Fixed support at node 0 with warping restrained
    nodes[0].nodal_support = NodalSupport(
        warping_condition=SupportCondition.fixed(),
    )

    # Create member chain
    members = []
    for i in range(n_elements):
        members.append(Member(start_node=nodes[i], end_node=nodes[i + 1], section=ipe300))

    model.add_member_set(MemberSet(members=members))

    # Apply torque about X-axis at the free end
    lc = model.create_load_case(name="End torque")
    NodalMoment(node=nodes[-1], load_case=lc, magnitude=T, direction=(1, 0, 0))

    print(f"\nRunning analysis: {label}  ({n_elements} elements) ...")
    model.run_analysis()

    # Extract twist at tip (last node)
    tip_node_id = str(nodes[-1].id)
    rx = model.resultsbundle.loadcases["End torque"].displacement_nodes[tip_node_id].rx
    return rx


# =============================================================================
# Run with and without warping
# =============================================================================
theta_sv = run_torsion_cantilever(include_warping=False, label="St. Venant only")
theta_vlasov = run_torsion_cantilever(include_warping=True, label="Vlasov warping")


# =============================================================================
# Analytical reference values
# =============================================================================
E = steel.e_mod
G = steel.g_mod
J = ipe300.j
I_w = ipe300.i_w if ipe300.i_w else 0.0

# St. Venant:
theta_sv_analytical = T * L / (G * J)

# Vlasov (cantilever, warping fixed at root, free at tip):
if I_w > 0:
    k = math.sqrt(G * J / (E * I_w))
    kL = k * L
    theta_vlasov_analytical = (T * L / (G * J)) * (1.0 - math.tanh(kL) / kL)
    bimoment_root = -T / k * math.tanh(kL)
else:
    theta_vlasov_analytical = theta_sv_analytical
    bimoment_root = 0.0


# =============================================================================
# Results comparison
# =============================================================================
print("\n" + "=" * 72)
print("RESULTS: Cantilever IPE300, L = {:.1f} m, T = {:.1f} kN·m".format(L, T / 1000))
print("=" * 72)

print(f"\n{'':35s} {'FERS':>14s} {'Analytical':>14s}")
print("-" * 72)

print(f"{'St. Venant θ_x [rad]':35s} {theta_sv:14.6f} {theta_sv_analytical:14.6f}")
print(
    f"{'St. Venant θ_x [deg]':35s} {math.degrees(theta_sv):14.4f} {math.degrees(theta_sv_analytical):14.4f}"
)

print(f"{'Vlasov θ_x [rad]':35s} {theta_vlasov:14.6f} {theta_vlasov_analytical:14.6f}")
print(
    f"{'Vlasov θ_x [deg]':35s} {math.degrees(theta_vlasov):14.4f} {math.degrees(theta_vlasov_analytical):14.4f}"  # noqa: E501
)

reduction = (1.0 - abs(theta_vlasov) / abs(theta_sv)) * 100 if theta_sv != 0 else 0
reduction_analytical = (1.0 - abs(theta_vlasov_analytical) / abs(theta_sv_analytical)) * 100

print(f"\nWarping reduces twist by:  FERS = {reduction:.1f}%    Analytical = {reduction_analytical:.1f}%")
if I_w > 0:
    print(f"  k = √(GJ/EIw) = {k:.4f} /m")
    print(f"  kL = {kL:.4f}")
    print(f"  Bimoment at root (analytical) = {bimoment_root:.2f} N·m²")

print("\n--- Validation ---")
if abs(theta_sv - theta_sv_analytical) / abs(theta_sv_analytical) < 0.01:
    print("St. Venant twist within 1% of analytical ✅")
else:
    print(
        f"St. Venant twist differs by "
        f"{abs(theta_sv - theta_sv_analytical)/abs(theta_sv_analytical)*100:.2f}% ❌"
    )

if abs(theta_vlasov - theta_vlasov_analytical) / abs(theta_vlasov_analytical) < 0.02:
    print("Vlasov twist within 2% of analytical     ✅")
else:
    print(
        f"Vlasov twist differs by "
        f"{abs(theta_vlasov - theta_vlasov_analytical)/abs(theta_vlasov_analytical)*100:.2f}% ❌"
    )
