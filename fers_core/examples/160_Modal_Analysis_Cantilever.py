import os
import math
from fers_core import Node, Member, FERS, Material, Section, MemberSet, NodalSupport, modal_analysis


# =============================================================================
# Example and Validation: Modal (Natural-Frequency) Analysis of a Cantilever
# =============================================================================
# Demonstrates the optional modal analysis added in solver 0.2.37. The solver
# solves K·phi = omega^2·M·phi alongside the static run and reports the lowest
# natural modes in `results.modal`.
#
# The fundamental bending frequency of a fixed-base cantilever is
#     f1 = beta1^2 / (2*pi) * sqrt(E*I / (rho*A*L^4)),   beta1 = 1.875104
# (Euler-Bernoulli). A square section makes the two bending planes degenerate.

# Step 1: Set up the model (in SI units so frequencies compare straight to theory)
# -------------------------------------------------------------------------------
E = 210.0e9          # Pa
RHO = 7850.0         # kg/m^3
B = 0.1              # square side [m]
L = 5.0              # cantilever length [m]
AREA = B * B
INERTIA = B**4 / 12.0

calculation_1 = FERS()

steel = Material(name="Steel", e_mod=E, g_mod=80.769e9, density=RHO, yield_stress=235e6)
section = Section(name="Square 100x100", material=steel, i_y=INERTIA, i_z=INERTIA, j=0.1406 * B**4, area=AREA)

# Chain of 10 equal beam elements along global X from the fixed base to the tip.
n_el = 10
nodes = [Node(L * i / n_el, 0, 0) for i in range(n_el + 1)]
nodes[0].nodal_support = NodalSupport()  # fully fixed base
members = [Member(start_node=nodes[i], end_node=nodes[i + 1], section=section) for i in range(n_el)]
calculation_1.add_member_set(MemberSet(members=members))

# Step 2: Request a modal analysis (lowest 4 modes)
# -------------------------------------------------
calculation_1.analysis.set_modal(modal_analysis(num_modes=4))

# Step 3: Run FERS calculation
# ----------------------------
file_path = os.path.join("json_input_solver", "160_Modal_Analysis_Cantilever.json")
os.makedirs(os.path.dirname(file_path), exist_ok=True)
calculation_1.save_to_json(file_path, indent=4)

print("Running the modal analysis...")
calculation_1.run_analysis()

modal = calculation_1.modal_results()
modes = modal["modes"]

# Step 4: Validate against the analytical fundamental frequency
# -------------------------------------------------------------
beta1 = 1.875104
f1_analytical = beta1**2 / (2 * math.pi) * math.sqrt(E * INERTIA / (RHO * AREA * L**4))
f1_fers = modes[0]["natural_frequency"]

print("\nNatural frequencies (Hz):")
for m in modes:
    print(f"  Mode {m['mode']}: f = {m['natural_frequency']:.4f} Hz, T = {m['period']:.4f} s")

print("\nComparison of results:")
print(f"Fundamental frequency (FERS): {f1_fers:.4f} Hz")
print(f"Fundamental frequency (Analytical): {f1_analytical:.4f} Hz")
if abs(f1_fers - f1_analytical) / f1_analytical < 0.02:
    print("Fundamental frequency matches the analytical solution ✅")
else:
    print("Fundamental frequency does NOT match the analytical solution ❌")


# =============================================================================
# Notes for Users
# =============================================================================
# 1. Modal analysis needs mass, which comes from the material density (and the
#    optional per-member `weight` override). Without density there is no mass.
# 2. Mode shapes are returned per node in `m["displacements"]`, normalized so
#    the largest translational component is 1 — handy for plotting.
# 3. `effective_mass` / `participation_factors` per global direction support
#    response-spectrum and participating-mass checks.
