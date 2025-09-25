import os
from fers_core import (
    Node,
    Member,
    FERS,
    Material,
    Section,
    MemberSet,
    NodalSupport,
)

from fers_core.loads.distributedload import DistributedLoad

# =============================================================================
# Example and Validation: Cantilever Beam with End Load
# =============================================================================

# Step 1: Set up the model
# -------------------------
# Create the main FERS object that will manage the analysis
calculation_1 = FERS()

# Define the geometry of the beam
node1 = Node(0, 0, 0)  # Simply supported side of the beam at x=0
node2 = Node(3, 0, 0)  # Intermediate node at x=3
node3 = Node(6, 0, 0)  # Simply supported side of the beam at x=6

# Define the material properties (Steel S235)
Steel_S235 = Material(name="Steel", e_mod=210e9, g_mod=80.769e9, density=7850, yield_stress=235e6)

# Define the beam cross-section (IPE 180)
section = Section(
    name="IPE 180 Beam Section", material=Steel_S235, i_y=0.819e-6, i_z=10.63e-6, j=0.027e-6, area=0.00196
)

# Create the beam element
beam1 = Member(start_node=node1, end_node=node2, section=section)
beam2 = Member(start_node=node2, end_node=node3, section=section)

# Apply a fixed support at the fixed end (node1)

fixed_support = NodalSupport()

node1.nodal_support = fixed_support
node3.nodal_support = fixed_support

# Add the beam to a member group
membergroup1 = MemberSet(members=[beam1, beam2])

# Add the member group to the calculation model
calculation_1.add_member_set(membergroup1)

# Step 2: Apply the load
# ----------------------
# Create a load case for the analysis
intermediate_load_case = calculation_1.create_load_case(name="Distributed Load")

# Apply a 1 kn/m uniform distributed load (global y-axis) along the beam
distributed_load = DistributedLoad(
    member=beam1,
    load_case=intermediate_load_case,
    magnitude=1000.0,  # 1000 N/m (example uniform load)
    direction=(0, -1, 0),  # Downward in the global Y-axis
)
distributed_load = DistributedLoad(
    member=beam2,
    load_case=intermediate_load_case,
    magnitude=1000.0,  # 1000 N/m (example uniform load)
    direction=(0, -1, 0),  # Downward in the global Y-axis
)


# Save the model to a file for FERS calculations
file_path = os.path.join("json_input_solver", "032_Fixed_Fixed_with_Uniform_Distributed_load.json")
os.makedirs(os.path.dirname(file_path), exist_ok=True)
calculation_1.save_to_json(file_path, indent=4)


# Step 3: Run FERS calculation
# ----------------------------
# Perform the analysis using the saved JSON model file
print("Running the analysis...")
calculation_1.run_analysis()
result_loadcase = calculation_1.results.loadcases["Distributed Load"]

# Extract results from the analysis
dy_fers = result_loadcase.displacement_nodes["2"].dy
Mz_fers_begin_end = result_loadcase.reaction_nodes["1"].nodal_forces.mz
Mz_fers_intermediate = result_loadcase.member_results["1"].end_node_forces.mz

# Step 4: Validate Results Against Analytical Solution
# ----------------------------------------------------
# Analytical solution parameters
W = 1000  # Uniform load in Newtons
L = 6  # Length of the beam in meters
E = 210e9  # Modulus of elasticity in Pascals
I = 10.63e-6  # Moment of inertia in m^4
x = L / 2  # Distance to the free end for max deflection and slope

# Calculate analytical solutions for deflection and moment
delta_analytical = -(W * L**4) / (384 * E * I)  # Max deflection
Mz_intermediate = (W * L**2) / 24  # Max moment at intermediate node
Mz_begin_end = (W * L**2) / 12  # Max moment at the fixed end

# Compare FERS results with analytical solutions
print("\nComparison of results:")
print(f"Deflection at middle node (FERS): {dy_fers:.6f} m")
print(f"Deflection at middle node (Analytical): {delta_analytical:.6f} m")
if abs(dy_fers - delta_analytical) < 1e-6:
    print("Deflection matches the analytical solution ✅")
else:
    print("Deflection does NOT match the analytical solution ❌")

print()

print(f"Bending moment at middle node (FERS): {Mz_fers_intermediate:.6f} Nm")
print(f"Bending moment at middle node (Analytical): {Mz_intermediate:.6f} Nm")
if abs(Mz_fers_intermediate - Mz_intermediate) < 1e-6:
    print("Bending moment matches the analytical solution ✅")
else:
    print("Bending moment does NOT match the analytical solution ❌")

print()


print(f"Reaction moment at begin (FERS): {Mz_fers_begin_end:.6f} Nm")
print(f"Reaction moment at begin (Analytical): {Mz_begin_end:.6f} Nm")
if abs(Mz_fers_begin_end - Mz_begin_end) < 1e-3:
    print("Reaction moment matches the analytical solution ✅")
else:
    print("Reaction moment does NOT match the analytical solution ❌")

print("\nAll results validated successfully!")

# =============================================================================
# Notes for Users
# =============================================================================
# This script is both an example and a validation tool.
# 1. It demonstrates how to set up and analyze a cantilever beam with an end load.
# 2. It validates the FERS results against analytical solutions for deflection and moment.
# 3. Run this script as-is to learn, or integrate it into your CI/CD pipeline for validation.
