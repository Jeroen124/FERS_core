from fers_core import Node, Member, FERS, Material, Section, MemberSet, NodalSupport, NodalLoad
import os

# =============================================================================
# Example and Validation: Cantilever Beam with Intermediate Load
# =============================================================================

# Step 1: Set up the model
# -------------------------
# Create the main FERS object that will manage the analysis
calculation_1 = FERS()

# Define the geometry of the beam
node1 = Node(0, 0, 0)  # Fixed end of the beam
node2 = Node(5, 0, 0)  # Free end of the beam, 5 meters away
intermediate_node = Node(3, 0, 0)  # Intermediate point for load application, 3 meters away

# Define the material properties (Steel S235)
Steel_S235 = Material(name="Steel", e_mod=210e9, g_mod=80.769e9, density=7850, yield_stress=235e6)

# Define the beam cross-section (IPE 180)
section = Section(
    name="IPE 180 Beam Section", material=Steel_S235, i_y=0.819e-6, i_z=10.63e-6, j=0.027e-6, area=0.00196
)

# Create the beam element
beam1 = Member(start_node=node1, end_node=intermediate_node, section=section)
beam2 = Member(start_node=intermediate_node, end_node=node2, section=section)

# Apply a fixed support at the fixed end (node1)
wall_support = NodalSupport()
node1.nodal_support = wall_support

# Add the beam to a member group
membergroup1 = MemberSet(members=[beam1, beam2])

# Add the member group to the calculation model
calculation_1.add_member_set(membergroup1)

# Step 2: Apply the intermediate load
# -----------------------------------
# Create a load case for the analysis
intermediate_load_case = calculation_1.create_load_case(name="Intermediate Load")

# Apply a 1 kN downward force (global y-axis) at the intermediate point
nodal_load = NodalLoad(
    node=intermediate_node, load_case=intermediate_load_case, magnitude=-1000, direction=(0, 1, 0)
)

# Save the model to a file for FERS calculations
file_path = os.path.join("json_input_solver", "002_Cantilever_with_Intermediate_Load.json")
calculation_1.save_to_json(file_path, indent=4)

# Step 3: Run FERS calculation
# ----------------------------
# Perform the analysis using the saved JSON model file
print("Running the analysis...")
calculation_1.run_analysis()

# Extract results from the analysis
results = calculation_1.results.loadcases["Intermediate Load"]

# Extract results from the analysis
# Displacement at the intermediate point in the y-direction
dy_fers_intermediate = results.displacement_nodes["3"].dy
# Displacement at the free end in the y-direction
dy_fers_end = results.displacement_nodes["2"].dy
# Reaction moment at the fixed end
Mz_fers = results.reaction_nodes["1"].nodal_forces.mz

# Step 4: Validate Results Against Analytical Solution
# ----------------------------------------------------
# Analytical solution parameters
F = 1000  # Force in Newtons
L = 5  # Length of the beam in meters
E = 210e9  # Modulus of elasticity in Pascals
I = 10.63e-6  # Moment of inertia in m^4
a = 3  # Distance to the intermediate point

# Calculate analytical solutions for deflection and moment (piecewise approach)
# For deflection and slope:
# ( 0 <= x <= a )
delta_analytical_intermediate = (-F * a**2 / (6 * E * I)) * (3 * a - a)  # Deflection at intermediate point
# ( a <= x <= L )
delta_analytical_end = ((-F * a**2) / (6 * E * I)) * (3 * L - a)  # Deflection at the free end

# Max moment:
M_max_analytical = F * a  # Max moment at the fixed end

# Compare FERS results with analytical solutions
print("\nComparison of results:")
print(f"Deflection at intermediate point (FERS): {dy_fers_intermediate:.6f} m")
print(f"Deflection at intermediate point (Analytical): {delta_analytical_intermediate:.6f} m")
if abs(dy_fers_intermediate - delta_analytical_intermediate) < 1e-6:
    print("Deflection at intermediate point matches the analytical solution ✅")
else:
    print("Deflection at intermediate point does NOT match the analytical solution ❌")

print(f"Deflection at free end (FERS): {dy_fers_end:.6f} m")
print(f"Deflection at free end (Analytical): {delta_analytical_end:.6f} m")
if abs(dy_fers_end - delta_analytical_end) < 1e-6:
    print("Deflection at free end matches the analytical solution ✅")
else:
    print("Deflection at free end does NOT match the analytical solution ❌")

print(f"Reaction moment at fixed end (FERS): {Mz_fers:.6f} Nm")
print(f"Reaction moment at fixed end (Analytical): {M_max_analytical:.6f} Nm")
if abs(Mz_fers - M_max_analytical) < 1e-3:
    print("Reaction moment matches the analytical solution ✅")
else:
    print("Reaction moment does NOT match the analytical solution ❌")

# =============================================================================
# Notes for User
# =============================================================================
# This script is both an example and a validation tool.
# 1. It demonstrates how to set up and analyze a cantilever beam with an intermediate load.
# 2. It validates the FERS results against analytical solutions for deflection and moment.
# 3. Run this script as-is to learn
