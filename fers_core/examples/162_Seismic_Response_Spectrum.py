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
    seismic_analysis,
    direct_spectrum,
    seismic_mass_source,
)


# =============================================================================
# Example and Validation: Seismic Analysis (EN 1998-1) of an SDOF "Lollipop"
# =============================================================================
# Demonstrates the optional seismic analysis added in solver 0.2.37. The solver
# runs a modal response spectrum analysis (MRSA, §4.3.3.3) and/or the lateral
# force method (§4.3.3.2) and reports `results.seismic`.
#
# Model: a vertical cantilever column (along Y) fixed at the base, carrying a
# dominant tip mass supplied as a gravity load case (mass = G_load / g). This is
# a single-degree-of-freedom oscillator with a closed-form period and base shear:
#     k  = 3*E*I / H^3            (cantilever tip stiffness)
#     T1 = 2*pi*sqrt(M / k)
#     Fb = M * Sd(T1)            (base shear)

# Step 1: Set up the model (SI units → reported base shear compares to theory)
# ---------------------------------------------------------------------------
E = 210.0e9          # Pa
INERTIA = 1.0e-4     # m^4
AREA = 0.01          # m^2
H = 4.0              # column height [m]
G = 9.81             # m/s^2
M_TIP = 10_000.0     # tip mass [kg]

calculation_1 = FERS()
steel = Material(name="Steel", e_mod=E, g_mod=80.769e9, density=7850, yield_stress=235e6)
section = Section(name="SQ", material=steel, i_y=INERTIA, i_z=INERTIA, j=1.0e-5, area=AREA)

base = Node(0, 0, 0)
top = Node(0, H, 0)
base.nodal_support = NodalSupport()  # fully fixed base
calculation_1.add_member_set(MemberSet(members=[Member(start_node=base, end_node=top, section=section)]))

# Step 2: Gravity load case → the seismic mass source (M_TIP * g downward at top)
# -------------------------------------------------------------------------------
gravity = calculation_1.create_load_case(name="Gravity")
NodalLoad(node=top, load_case=gravity, magnitude=M_TIP * G, direction=(0, -1, 0))

# Step 3: Request seismic analysis — both MRSA and lateral force, X direction
# ---------------------------------------------------------------------------
# DirectParameters design spectrum: ag=S=1, Tb=0.1, Tc=0.5, Td=2, q=1, beta=0.2.
spectrum = direct_spectrum(ag=1.0, s=1.0, tb=0.1, tc=0.5, td=2.0, q=1.0, beta=0.2)
calculation_1.analysis.set_seismic(
    seismic_analysis(
        method="BOTH",
        num_modes=3,
        spectrum_x=spectrum,
        # Isolate the tip mass for a clean SDOF check (no structural self-mass).
        include_structural_mass=False,
        mass_sources=[seismic_mass_source(gravity.id, psi=1.0)],
        directions=["X"],
    )
)

# Step 4: Run FERS calculation
# ----------------------------
file_path = os.path.join("json_input_solver", "162_Seismic_Response_Spectrum.json")
os.makedirs(os.path.dirname(file_path), exist_ok=True)
calculation_1.save_to_json(file_path, indent=4)

print("Running the seismic analysis...")
calculation_1.run_analysis()

seismic = calculation_1.seismic_results()
mrsa_dir = seismic["modal_response_spectrum"]["per_direction"][0]
lateral_dir = seismic["lateral_force"]["per_direction"][0]

# Step 5: Validate against the closed-form SDOF response
# ------------------------------------------------------
k = 3.0 * E * INERTIA / H**3
T1 = 2.0 * math.pi * math.sqrt(M_TIP / k)
Sd = max(2.5 * 0.5 / T1, 0.2)  # constant-velocity branch: ag*S*(2.5/q)*(Tc/T), floor beta*ag
Fb_analytical = M_TIP * Sd

print("\nSeismic response (X direction):")
print(f"  Fundamental period T1: {T1:.4f} s")
print(f"  Total seismic mass: {mrsa_dir['total_seismic_mass']:.1f} kg (tip mass {M_TIP:.0f} kg)")
print(f"  Participating mass ratio: {mrsa_dir['participating_mass_ratio']:.3f}")
print(f"  MRSA base shear: {mrsa_dir['base_shear']:.1f} N")
print(f"  Lateral-force base shear: {lateral_dir['base_shear']:.1f} N")
print(f"  Analytical base shear (M·Sd(T1)): {Fb_analytical:.1f} N")

ok_mrsa = abs(mrsa_dir["base_shear"] - Fb_analytical) / Fb_analytical < 0.05
ok_lat = abs(lateral_dir["base_shear"] - Fb_analytical) / Fb_analytical < 0.05
print("\nComparison of results:")
if ok_mrsa:
    print("MRSA base shear matches the analytical solution ✅")
else:
    print("MRSA base shear does NOT match the analytical solution ❌")
if ok_lat:
    print("Lateral-force base shear matches the analytical solution ✅")
else:
    print("Lateral-force base shear does NOT match the analytical solution ❌")


# =============================================================================
# Notes for Users
# =============================================================================
# 1. Seismic mass comes from `mass_sources` (gravity load cases × psi) plus the
#    optional structural self-mass (density·area). Here self-mass is off to keep
#    a clean single-mass oscillator.
# 2. Use `eurocode_spectrum(...)` for an EN 1998-1 ground-type preset, or
#    `custom_spectrum(points)` for an arbitrary (T, Sa) table.
# 3. `directions=["X","Y","Z"]` analyses several excitation directions; results
#    are combined per `directional_combination` (SRSS default, or PERCENT_30).
# 4. Each direction's combined response is a full result set
#    (`mrsa_dir["combined"]`) with displacements, member forces and reactions.
