import os
os.chdir('..')  

from fers_core.nodes.node import Node
from fers_core.members.member import Member
from fers_core.fers.fers import FERS

# Create nodes
node1 = Node(0, 0, 0)  # Fixed end
node2 = Node(5, 0, 0)  # Free end

# Create member
beam = Member(node1, node2)

# Create analysis object
analysis_1 = FERS()

# Add nodes and member to the analysis
analysis_1.add_node(node1)
analysis_1.add_node(node2)
analysis_1.add_member(beam)

# Apply boundary conditions (fixed at node1)
analysis_1.add_support(node1, dx=0, dy=0, dz=0, rx=0, ry=0, rz=0)

# Apply end load at node2 (100 kN downward force)
analysis_1.add_load(node2, fy=-100)

# Run analysis
analysis_1.analyze()

# Print results
print("Displacement at free end (node2):")
print(f"dy = {node2.displacement[1]:.6f} m")

print("\nReaction forces at fixed end (node1):")
print(f"Fy = {node1.reaction_force[1]:.2f} kN")
print(f"Mz = {node1.reaction_moment[2]:.2f} kN·m")

# Calculate and print maximum bending stress
I = beam.moment_of_inertia_z  # Assuming a default cross-section
y_max = beam.height / 2
M_max = abs(node1.reaction_moment[2])
sigma_max = M_max * y_max / I

print(f"\nMaximum bending stress: {sigma_max:.2f} MPa")
