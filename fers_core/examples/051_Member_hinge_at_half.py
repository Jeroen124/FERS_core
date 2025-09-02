import os
from fers_core import Node, Member, FERS, Material, Section, MemberSet, NodalSupport, NodalLoad
from fers_core.members.memberhinge import MemberHinge

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
node2 = Node(2.5, 0.0, 0.0)  # junction (end of rigid link, start of flexible beam)
node3 = Node(5.0, 0.0, 0.0)  # free end

# Support at node1 (fixed translations and rotations)
node1.nodal_support = NodalSupport()

# Define the material properties (Steel S235)
Steel_S235 = Material(name="Steel", e_mod=210e9, g_mod=80.769e9, density=7850, yield_stress=235e6)

# Define the beam cross-section (IPE 180)
section = Section(
    name="IPE 180 Beam Section", material=Steel_S235, i_y=0.819e-6, i_z=10.63e-6, j=0.027e-6, area=0.00196
)

# Rotational spring at the start of the flexible member (around local z)
# Choose stiffness to target a specific root rotation under the tip force.
tip_force_newton = 1000.0  # N
flexible_length_meter = 2.5  # m  (length of the NORMAL member node2->node3)
target_root_rotation_rad = 0.1
k_phi_z = (tip_force_newton * flexible_length_meter) / target_root_rotation_rad  # N·m/rad

start_hinge = MemberHinge(hinge_type="SPRING_Z", rotational_release_mz=k_phi_z)

# Members
rigid_link = Member(start_node=node1, end_node=node2, member_type="RIGID")
flexible_beam = Member(start_node=node2, end_node=node3, section=section, start_hinge=start_hinge)

# Add members to the model
member_set = MemberSet(members=[rigid_link, flexible_beam])
calculation_1.add_member_set(member_set)

# If your serializer requires explicit collection of hinges, uncomment:
# calculation_1.memberhinges.append(start_hinge)

# Step 2: Apply the load
# ----------------------
load_case = calculation_1.create_load_case(name="End Load")

# 1 kN downward at the free end
NodalLoad(
    node=node3,
    load_case=load_case,
    magnitude=-1000.0,  # negative with +Y direction means downward
    direction=(0.0, 1.0, 0.0),
)

# Save the model (useful for reproducibility or external solver runs)
file_path = os.path.join("json_input_solver", "051_Member_hinge_at_half.json")
calculation_1.save_to_json(file_path, indent=4)

# Step 3: Run FERS calculation
# ----------------------------
print("Running the analysis...")
calculation_1.run_analysis()
results = calculation_1.results.loadcases["End Load"]

# Extract FERS results
deflection_y_tip_fers = results.displacement_nodes["3"].dy
rotation_tip_fers = results.displacement_nodes["3"].rz
reaction_moment_support_fers = results.reaction_nodes["1"].nodal_forces.mz

# Step 4: Validate against analytical solution
# --------------------------------------------
# For a cantilever of length L with a root rotational spring k_phi:
#   Root rotation:        φ0 = (F * L) / k_phi
#   Tip rotation:         φ_tip = (F * L**2) / (2 * E * I) + φ0
#   Tip deflection:       δ_tip = (F * L**3) / (3 * E * I) + φ0 * L
#   Reaction moment:      M_support = F * L    (statically determinate)
#
# Here, L is the flexible span (node2->node3), not the total node1->node3 distance.

E = Steel_S235.e_mod
I = section.i_z  # bending about local z for vertical loading

L = flexible_length_meter
F = tip_force_newton
k = k_phi_z

root_rotation_expected = (F * L) / k
tip_rotation_expected = -((F * L**2) / (2.0 * E * I) + root_rotation_expected)
tip_deflection_expected = -((F * L**3) / (3.0 * E * I) + root_rotation_expected * L)
reaction_moment_support_expected = F * L * 2

# Print comparisons
print("\nComparison of results:")
print(f"Spring stiffness used k_phi_z:             {k:,.3f} N·m/rad")
print(f"Expected root rotation φ0 (analytical):    {root_rotation_expected:.6f} rad")

print(f"\nTip deflection δ_y (FERS):                 {deflection_y_tip_fers:.6f} m")
print(f"Tip deflection δ_y (analytical):           {tip_deflection_expected:.6f} m")
if abs(deflection_y_tip_fers - tip_deflection_expected) < 1e-6:
    print("Tip deflection matches the analytical solution ✅")
else:
    print("Tip deflection does NOT match the analytical solution ❌")

print(f"\nTip rotation φ_tip (FERS):                  {rotation_tip_fers:.6f} rad")
print(f"Tip rotation φ_tip (analytical):            {tip_rotation_expected:.6f} rad")
if abs(rotation_tip_fers - tip_rotation_expected) < 1e-6:
    print("Tip rotation matches the analytical solution ✅")
else:
    print("Tip rotation does NOT match the analytical solution ❌")

print(f"\nSupport reaction moment Mz (FERS):          {reaction_moment_support_fers:.6f} N·m")
print(f"Support reaction moment Mz (analytical):    {reaction_moment_support_expected:.6f} N·m")
if abs(reaction_moment_support_fers - reaction_moment_support_expected) < 1e-3:
    print("Support reaction moment matches the analytical solution ✅")
else:
    print("Support reaction moment does NOT match the analytical solution ❌")


# =============================================================================
# Notes for Users
# =============================================================================
# 1) This example shows how to model a root rotational spring using MemberHinge while
#    keeping a rigid link from the fixed support to the spring location.
# 2) The analytical checks use closed-form expressions for a cantilever with a root spring.
# 3) You can tune k_phi_z to target a desired root rotation under the applied tip load.
