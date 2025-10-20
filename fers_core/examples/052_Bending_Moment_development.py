import os
from fers_core import Node, Member, FERS, Material, MemberHinge, Section, MemberSet, NodalSupport, NodalLoad


def print_displacements_for_loadcase(results_for_loadcase):
    displacement_dict = results_for_loadcase.displacement_nodes

    # Sort nodes numerically if possible
    def sort_key(node_key):
        try:
            return (0, int(node_key))
        except (TypeError, ValueError):
            return (1, str(node_key))

    print("\nNodal displacements and rotations:")
    print("Node |     dx [m]   |     dy [m]   |     dz [m]   |     rx [rad] |     ry [rad] |     rz [rad]")
    print("-----+--------------+--------------+--------------+--------------+--------------+--------------")

    for node_id in sorted(displacement_dict.keys(), key=sort_key):
        d = displacement_dict[node_id]
        print(
            f"{node_id:>4} | {d.dx:>12.6e} | {d.dy:>12.6e} | {d.dz:>12.6e} | "
            f"{d.rx:>12.6e} | {d.ry:>12.6e} | {d.rz:>12.6e}"
        )


def print_bending_moments_for_loadcase(results_for_loadcase):
    member_results_dict = results_for_loadcase.member_results

    # Sort by numeric member identifier if possible, while remaining robust to non-numeric keys
    def sort_key(member_key):
        try:
            return (0, int(member_key))
        except (TypeError, ValueError):
            return (1, str(member_key))

    print("\nBending moments per member (local z-axis):")
    print("Member | Mz_start [N·m] | Mz_end [N·m] | Mz_min [N·m] | Mz_max [N·m]")
    print("-------+-----------------+--------------+--------------+--------------")

    for member_id in sorted(member_results_dict.keys(), key=sort_key):
        member_result = member_results_dict[member_id]

        bending_moment_start = member_result.start_node_forces.mz
        bending_moment_end = member_result.end_node_forces.mz
        bending_moment_min = member_result.minimums.mz
        bending_moment_max = member_result.maximums.mz

        print(
            f"{member_id:>6} | {bending_moment_start:>15.6f} | {bending_moment_end:>12.6f} | "
            f"{bending_moment_min:>12.6f} | {bending_moment_max:>12.6f}"
        )


def print_shear_forces_for_loadcase(results_for_loadcase):
    member_results_dict = results_for_loadcase.member_results

    # Sort by numeric member identifier if possible, while remaining robust to non-numeric keys
    def sort_key(member_key):
        try:
            return (0, int(member_key))
        except (TypeError, ValueError):
            return (1, str(member_key))

    print("\nShear forces per member (local y- and z-axes):")
    print(
        "Member | Vy_start [N] | Vy_end [N] | Vy_min [N] | Vy_max [N] | "
        "Vz_start [N] | Vz_end [N] | Vz_min [N] | Vz_max [N]"
    )
    print(
        "-------+--------------+------------+------------+------------+"
        "--------------+------------+------------+------------"
    )

    for member_id in sorted(member_results_dict.keys(), key=sort_key):
        member_result = member_results_dict[member_id]

        # Local y shear (Vy)
        vy_start = member_result.start_node_forces.fy
        vy_end = member_result.end_node_forces.fy
        vy_min = member_result.minimums.fy
        vy_max = member_result.maximums.fy

        # Local z shear (Vz)
        vz_start = member_result.start_node_forces.fz
        vz_end = member_result.end_node_forces.fz
        vz_min = member_result.minimums.fz
        vz_max = member_result.maximums.fz

        print(
            f"{member_id:>6} | {vy_start:>12.6f} | {vy_end:>10.6f} | {vy_min:>10.6f} | {vy_max:>10.6f} | "
            f"{vz_start:>12.6f} | {vz_end:>10.6f} | {vz_min:>10.6f} | {vz_max:>10.6f}"
        )


# =============================================================================
# Example and Validation: Cantilever With Root Rotational Spring (via MemberHinge)
# =============================================================================
# Model: node1 --[RIGID]--> node2 s--[NORMAL + spring at start]--> node3
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
node2 = Node(2.5, 0.0, 0.0)  # hinge
node3 = Node(5.0, 0.0, 0.0)  # node

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
target_root_rotation_rad = 0.01
k_phi_z = (tip_force_newton * flexible_length_meter) / target_root_rotation_rad  # N·m/rad

start_hinge = MemberHinge(hinge_type="SPRING_Z", rotational_release_mz=k_phi_z)

# Members
flexible_beam_1 = Member(start_node=node1, end_node=node2, section=section)
flexible_beam_2 = Member(start_node=node2, end_node=node3, section=section, start_hinge=start_hinge)
# flexible_beam_2 = Member(start_node=node2, end_node=node3, section=section)
# flexible_beam_4 = Member(start_node=node4, end_node=node5, section=section, start_hinge=start_hinge)

# Add members to the model
member_set = MemberSet(members=[flexible_beam_1, flexible_beam_2])
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
    direction=(0.0, -1.0, 0.0),
)

# Save the model (useful for reproducibility or external solver runs)
file_path = os.path.join("json_input_solver", "052_Bending_Moment_development.json")
os.makedirs(os.path.dirname(file_path), exist_ok=True)
calculation_1.save_to_json(file_path, indent=4)

# Step 3: Run FERS calculation
# ----------------------------
print("Running the analysis...")
calculation_1.run_analysis()
results = calculation_1.resultsbundle.loadcases["End Load"]

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
results = calculation_1.resultsbundle.loadcases["End Load"]
print_bending_moments_for_loadcase(results)
print_shear_forces_for_loadcase(results)
print_displacements_for_loadcase(results)
