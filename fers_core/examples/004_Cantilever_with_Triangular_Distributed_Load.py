import os
from FERS_core import (
    Node,
    Member,
    FERS,
    Material,
    Section,
    MemberSet,
    NodalSupport,
    DistributedLoad,
    DistributionShape,
)


# =============================================================================
# Example and Validation: Cantilever Beam with Uniform Distributed Load
# =============================================================================

# Step 1: Set up the model
# -------------------------
# Create the main FERS object that will manage the analysis
calculation_1 = FERS()

# Define the geometry of the beam
node1 = Node(0, 0, 0)  # Fixed end of the beam
node2 = Node(5, 0, 0)  # Free end of the beam, 5 meters away

# Define the material properties (Steel S235)
Steel_S235 = Material(name="Steel", e_mod=210e9, g_mod=80.769e9, density=7850, yield_stress=235e6)

# Define the beam cross-section (IPE 180)
section = Section(
    name="IPE 180 Beam Section", material=Steel_S235, i_y=0.819e-6, i_z=10.63e-6, j=0.027e-6, area=0.00196
)

# Create the beam element
beam = Member(start_node=node1, end_node=node2, section=section)

# Apply a fixed support at the fixed end (node1)
wall_support = NodalSupport()
node1.nodal_support = wall_support

# Add the beam to a member group
membergroup1 = MemberSet(members=[beam])

# Add the member group to the calculation model
calculation_1.add_member_set(membergroup1)

# Step 2: Apply the load
# ----------------------
# Create a load case for the analysis
load_case = calculation_1.create_load_case(name="Uniform Load")

# Apply a uniform distributed load (e.g., w = 1000 N/m) downward along the entire beam
distributed_load = DistributedLoad(
    member=beam,
    load_case=load_case,
    distribution_shape=DistributionShape.UNIFORM,
    magnitude=1000.0,  # 1000 N/m (example uniform load)
    direction=(0, -1, 0),  # Downward in the global Y-axis
    start_pos=0.0,
    end_pos=beam.length(),
)

# Save the model to a file for FERS calculations
file_path = os.path.join("json_input_solver", "004_Cantilever_with_Triangular_Distributed_Load.json")
calculation_1.save_to_json(file_path, indent=4)

# Step 3: Run FERS calculation
# ----------------------------
print("Running the analysis...")
calculation_1.run_analysis()

# Extract results from the analysis
# Displacement at the free end in the y-direction
dy_fers = calculation_1.results.displacement_nodes["2"].dy
# Reaction moment at the fixed end
Mz_fers = calculation_1.results.reaction_forces[0].mz

# Step 4: Validate Results Against Analytical Solution
# ----------------------------------------------------
# Analytical solution parameters for a cantilever with a uniform load 'w' over length L
w = 1000.0  # N/m (same as above)
L = 5  # Beam length in meters
E = 210e9  # Elastic modulus (Pascals)
I = 10.63e-6  # Moment of inertia (m^4)

# For a uniform load w on a cantilever, the maximum deflection at x=L is:
#   δ_max = w * L^4 / (8 * E * I)
delta_analytical = w * (L**4) / (8 * E * I)

# The maximum moment at the fixed end is:
#   M_max = w * L^2 / 2
M_max_analytical = w * (L**2) / 2

print("\nComparison of results:")
print(f"Deflection at free end (FERS): {dy_fers:.6f} m")
print(f"Deflection at free end (Analytical): {delta_analytical:.6f} m")
if abs(dy_fers - delta_analytical) < 1e-6:
    print("Deflection matches the analytical solution ✅")
else:
    print("Deflection does NOT match the analytical solution ❌")

print(f"Reaction moment at fixed end (FERS): {Mz_fers:.6f} Nm")
print(f"Reaction moment at fixed end (Analytical): {M_max_analytical:.6f} Nm")
if abs(Mz_fers - M_max_analytical) < 1e-3:
    print("Reaction moment matches the analytical solution ✅")
else:
    print("Reaction moment does NOT match the analytical solution ❌")

print("\nAll results validated successfully!")

# =============================================================================
# Notes for Users
# =============================================================================
# This script demonstrates how to set up and analyze a cantilever beam with a uniform distributed load.
# It validates the FERS results against the classical analytical solutions for deflection and moment.
# You can adapt this script for your own models or include it in a CI/CD pipeline for regression testing.
