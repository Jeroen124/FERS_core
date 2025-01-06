import os
from FERS_core import Node, Member, FERS, Material, Section, MemberSet, NodalSupport, NodalLoad


# =============================================================================
# Creating a cantilever with an end_load
# =============================================================================

# Create analysis object
calculation_1 = FERS()


# Create nodes
node1 = Node(0, 0, 0)  # Connected to wall
node2 = Node(0, 4, 0)  # Hinged connection
node3 = Node(3, 0, 0)  # Connected to wall

# Create material
Steel_S235 = Material(name="Steel", e_mod=210e9, g_mod=80.769e9, density=7850, yield_stress=235e6)

# Create a section
# For example IPE 180 - A:

ipe_section = Section.create_ipe_section(
    name="IPE 180 Beam Section",
    material=Steel_S235,
    h=0.177,
    b=0.091,
    t_f=0.0065,
    t_w=0.0043,
    r=0.009,
)

# Create member
beam_A = Member(start_node=node1, end_node=node3, section=ipe_section)
beam_B = Member(start_node=node2, end_node=node3, section=ipe_section)

# Creating a boundary conditions (by default all 6 d.o.f. are constraint)
wall_support = NodalSupport()

# Assigning the nodal_support to the correct node.
node1.nodal_support = wall_support
node2.nodal_support = wall_support

# =============================================================================
# Now that the geometrical part is created. Lets create the model and the loadcases
# =============================================================================
# Create a memberset holding the beam
membergroup1 = MemberSet(members=[beam_A])
membergroup2 = MemberSet(members=[beam_B])

# Adding the memberset to the model
calculation_1.add_member_set(membergroup1)
calculation_1.add_member_set(membergroup2)

# Create a loadcase for the end load
end_load_case = calculation_1.create_load_case(name="End Load")

# Apply end load at node2 1 kN downward force (global y-axis) to the loadcase
nodal_load = NodalLoad(node=node3, load_case=end_load_case, magnitude=150000, direction=(0, -1, 0))

file_path = os.path.join("examples", "json_input_solver", "22_two_bar_truss_with_visualization.json")
calculation_1.save_to_json(file_path, indent=4)


# Run analysis
# result = FERS_calculation(calculation_1)

# # Print results
# print("Displacement at free end (node2):")
# print(f"dy = {node2.displacement[1]:.6f} m")

# print("\nReaction forces at fixed end (node1):")
# print(f"Fy = {node1.reaction_force[1]:.2f} kN")
# print(f"Mz = {node1.reaction_moment[2]:.2f} kN·m")

# # With the use of beam equations https://mechanicalc.com/reference/beam-analysis


# # Calculate and print maximum bending stress
# i_z = beam.moment_of_inertia_z
# y_max = beam.height / 2
# M_max = abs(node1.reaction_moment[2])
# sigma_max = M_max * y_max / i_z

# print(f"\nMaximum bending stre
