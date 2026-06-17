import os
import math
from fers_core import (
    Node,
    Member,
    FERS,
    Material,
    Section,
    MemberSet,
    NodalSupport,
    NodalLoad,
    buckling_analysis,
    load_case_ref,
)


# =============================================================================
# Example and Validation: Linear (Eigenvalue) Buckling of an Euler Column
# =============================================================================
# Demonstrates the optional linear buckling analysis added in solver 0.2.37.
# The solver solves K·phi = lambda·(-K_g)·phi where K_g is the geometric
# stiffness from a reference load's first-order stress state, and reports the
# critical load factors alpha_cr in `results.buckling`.
#
# For a pinned-pinned column the Euler critical load is P_cr = pi^2*E*I / L^2,
# so with a reference axial load P_ref the reported alpha_cr = P_cr / P_ref.

# Step 1: Set up the model (SI units)
# -----------------------------------
E = 210.0e9          # Pa
B = 0.1              # square side [m]
L = 5.0              # column length [m]
P_REF = 1000.0       # reference axial compression [N]
AREA = B * B
INERTIA = B**4 / 12.0

calculation_1 = FERS()
steel = Material(name="Steel", e_mod=E, g_mod=80.769e9, density=7850, yield_stress=235e6)
section = Section(name="Square 100x100", material=steel, i_y=INERTIA, i_z=INERTIA, j=0.1406 * B**4, area=AREA)

# Vertical-free chain of 10 elements along global X.
n_el = 10
nodes = [Node(L * i / n_el, 0, 0) for i in range(n_el + 1)]
members = [Member(start_node=nodes[i], end_node=nodes[i + 1], section=section) for i in range(n_el)]

# Pinned-pinned: both ends hold the lateral translations and torsion (RX),
# bending rotations (RY/RZ) are free; the loaded tip is also free to shorten
# axially (X) so a compression develops. Directions not listed default to Fixed.
pinned_base = NodalSupport(
    displacement_conditions={"X": "Fixed", "Y": "Fixed", "Z": "Fixed"},
    rotation_conditions={"X": "Fixed", "Y": "Free", "Z": "Free"},
)
pinned_tip = NodalSupport(
    displacement_conditions={"X": "Free", "Y": "Fixed", "Z": "Fixed"},
    rotation_conditions={"X": "Fixed", "Y": "Free", "Z": "Free"},
)
nodes[0].nodal_support = pinned_base
nodes[-1].nodal_support = pinned_tip
calculation_1.add_member_set(MemberSet(members=members))

# Step 2: Reference load case (axial compression at the tip) + buckling request
# -----------------------------------------------------------------------------
axial = calculation_1.create_load_case(name="Axial")
NodalLoad(node=nodes[-1], load_case=axial, magnitude=P_REF, direction=(-1, 0, 0))
calculation_1.analysis.set_buckling(buckling_analysis(num_modes=2, reference=load_case_ref(axial.id)))

# Step 3: Run FERS calculation
# ----------------------------
file_path = os.path.join("json_input_solver", "161_Buckling_Euler_Column.json")
os.makedirs(os.path.dirname(file_path), exist_ok=True)
calculation_1.save_to_json(file_path, indent=4)

print("Running the buckling analysis...")
calculation_1.run_analysis()

buckling = calculation_1.buckling_results()
modes = buckling["modes"]

# Step 4: Validate against the Euler critical load factor
# -------------------------------------------------------
p_cr = math.pi**2 * E * INERTIA / L**2
alpha_analytical = p_cr / P_REF
alpha_fers = modes[0]["critical_load_factor"]

print("\nCritical load factors alpha_cr:")
for m in modes:
    print(f"  Mode {m['mode']}: alpha_cr = {m['critical_load_factor']:.3f}")

print("\nComparison of results:")
print(f"alpha_cr (FERS): {alpha_fers:.3f}")
print(f"alpha_cr (Analytical, pi^2 EI / L^2 / P_ref): {alpha_analytical:.3f}")
if abs(alpha_fers - alpha_analytical) / alpha_analytical < 0.03:
    print("Critical load factor matches the analytical solution ✅")
else:
    print("Critical load factor does NOT match the analytical solution ❌")


# =============================================================================
# Notes for Users
# =============================================================================
# 1. The reference load can be a load case (`load_case_ref`) or a load
#    combination (`load_combination_ref`). Its first-order axial forces drive
#    K_g, so alpha_cr scales the *whole* reference load to buckling.
# 2. Buckling mode shapes are in `m["displacements"]` (normalized), useful for
#    spotting the governing buckling mechanism.
