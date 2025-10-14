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
)

# =============================================================================
# Example and Validation: Cantilever With Root Rotational Spring (via MemberHinge)
# =============================================================================
# Model: node1 --[RIGID]--> node2 --[NORMAL + spring at start]--> node3
# Support: full fixity at node1 (translations and rotations)
# Load: 1 kN downward at the free end (node3)
#
# This is mechanically equivalent to a cantilever of length L with a rotational
# spring at its fixed/root end. The rigid member transmits the support DOFs to
# node2; the MemberHinge provides a rotational spring around local z at the
# start of the flexible member.
# =============================================================================

# Step 1: Set up the model
# ------------------------
calculation_1 = FERS()

# Geometry
node1 = Node(0.0, 0.0, 0.0)  # support end
node2 = Node(2.5, 0.0, 0.0)  # node for applying load
node3 = Node(5.0, 0.0, 0.0)  # free end

# Support at node1 and node 3, for stability fix displacement at node 2 (fixed translations and rotations)
node1.nodal_support = NodalSupport()
node2.nodal_support = NodalSupport(
    displacement_conditions={
        "X": SupportCondition.free(),
        "Y": SupportCondition.fixed(),
        "Z": SupportCondition.fixed(),
    }
)
node3.nodal_support = NodalSupport()

# Define the material properties (Steel S235)
Steel_S235 = Material(name="Steel", e_mod=210e9, g_mod=80.769e9, density=7850, yield_stress=235e6)

# Define the beam cross-section (IPE 180)
section = Section(
    name="IPE 180 Beam Section", material=Steel_S235, i_y=0.819e-6, i_z=10.63e-6, j=0.027e-6, area=0.00196
)

# Add a force in the middle node
mid_force_newton = 1  # N

# Members
rope_1 = Member(start_node=node1, end_node=node2, section=section, member_type="TENSION")
rope_2 = Member(start_node=node2, end_node=node3, section=section, member_type="TENSION")

# Add members to the model
member_set = MemberSet(members=[rope_1, rope_2])
calculation_1.add_member_set(member_set)


# If your serializer requires explicit collection of hinges, uncomment:
# calculation_1.memberhinges.append(start_hinge)

# Step 2: Apply the load
# ----------------------
load_case = calculation_1.create_load_case(name="Mid Load")

# 1 kN in the middle of the two ropes
NodalLoad(
    node=node2,
    load_case=load_case,
    magnitude=mid_force_newton,
    direction=(1.0, 0.0, 0.0),
)

# Save the model (useful for reproducibility or external solver runs)
file_path = os.path.join("json_input_solver", "061_Tension_member.json")
os.makedirs(os.path.dirname(file_path), exist_ok=True)
calculation_1.save_to_json(file_path, indent=4)

# Step 3: Run FERS calculation
# ----------------------------
print("Running the analysis...")
calculation_1.run_analysis()
results = calculation_1.resultsbundle.loadcases["Mid Load"]

# Extract FERS results
displacement_node2_dx_fers = results.displacement_nodes["2"].dx
reaction_node1_fx_fers = results.reaction_nodes["1"].nodal_forces.fx
reaction_node3_fx_fers = results.reaction_nodes["3"].nodal_forces.fx

# Step 4: Validate Against Analytical Solution
# --------------------------------------------
elastic_modulus = Steel_S235.e_mod
cross_section_area = section.area
member_length = 2.5  # meters (each tension member length)
applied_force = -mid_force_newton  # Newtons

# Analytical expectations:
# - Displacement at node 2 along global X: u = F * L / (A * E)
# - Reaction at node 1 in Fx: -F
# - Reaction at node 3 in Fx: 0 (tension-only member cannot carry compression)
displacement_node2_dx_expected = (applied_force * member_length) / (cross_section_area * elastic_modulus)
reaction_node1_fx_expected = applied_force
reaction_node3_fx_expected = 0.0


def relative_error(expected_value: float, actual_value: float) -> float:
    denominator = max(abs(expected_value), 1.0)
    return abs(actual_value - expected_value) / denominator


# Tolerances (adjust if your solver accuracy is different)
absolute_tolerance_displacement = 1e-9
absolute_tolerance_reaction = 1e-6
relative_tolerance = 1e-6

print("\nComparison of results:")
print(f"Displacement at node 2 in X (FERS):       {displacement_node2_dx_fers:.9e} m")
print(f"Displacement at node 2 in X (Analytical):  {displacement_node2_dx_expected:.9e} m")
if (
    abs(displacement_node2_dx_fers - displacement_node2_dx_expected) < absolute_tolerance_displacement
    or relative_error(displacement_node2_dx_expected, displacement_node2_dx_fers) < relative_tolerance
):
    print("Displacement at node 2 matches the analytical solution ✅")
else:
    print("Displacement at node 2 does NOT match the analytical solution ❌")

print(f"\nReaction force at node 1, Fx (FERS):       {reaction_node1_fx_fers:.6f} N")
print(f"Reaction force at node 1, Fx (Analytical):  {reaction_node1_fx_expected:.6f} N")
if (
    abs(reaction_node1_fx_fers - reaction_node1_fx_expected) < absolute_tolerance_reaction
    or relative_error(reaction_node1_fx_expected, reaction_node1_fx_fers) < relative_tolerance
):
    print("Reaction at node 1 matches the analytical solution ✅")
else:
    print("Reaction at node 1 does NOT match the analytical solution ❌")

print(f"\nReaction force at node 3, Fx (FERS): {reaction_node3_fx_fers:.6f} N")
print(f"Reaction force at node 3, Fx (Analytical):  {reaction_node3_fx_expected:.6f} N")
if (
    abs(reaction_node3_fx_fers - reaction_node3_fx_expected) < absolute_tolerance_reaction
    or relative_error(reaction_node3_fx_expected, reaction_node3_fx_fers) < relative_tolerance
):
    print("Reaction at node 3 matches the analytical expectation (tension-only member cannot push) ✅")
else:
    print("Reaction at node 3 does NOT match the analytical expectation ❌")

# =============================================================================
# Notes for User
# =============================================================================
# - This example models two colinear tension-only members with a load at the middle node,
#   which should place only one member in tension under a positive global X load.
# - Ensure comments and units match your applied load direction and magnitude.
#   (This script applies the load along global X using 'mid_force_newton'.)
