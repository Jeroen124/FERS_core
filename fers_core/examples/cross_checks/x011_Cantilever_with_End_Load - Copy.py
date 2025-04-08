from PyNite import FEModel3D

# Render the model and plot the `Mx` moments.
from PyNite.Rendering import Renderer

# Create a new finite element model
model = FEModel3D()

# Add nodes (x, y, z coordinates)
model.add_node("N1", 0, 0, 0)
model.add_node("N2", 3, 0, 0)
model.add_node("N3", 6, 0, 0)
# model.add_auxnode("N_aux", 5, 50, 0)

# Add a beam member between the nodes
model.add_material("Steel", E=210e9, G=80.769e9, nu=0.3, rho=7850)
# model.add_section("IPE180", A=0.00196, Iy=10.63e-6, Iz=0.819e-6, J=0.027e-6)
model.add_section("IPE180", A=0.00196, Iy=0.819e-6, Iz=10.63e-6, J=0.027e-6)


# model.add_member("M1", "N1", "N2", material_name="Steel", section_name="IPE180", aux_node="N_aux")
model.add_member("M1", "N1", "N2", material_name="Steel", section_name="IPE180")
model.add_member("M2", "N2", "N3", material_name="Steel", section_name="IPE180")

# Add supports
model.def_support("N1", True, True, True, True, True, False)
model.def_support("N3", True, True, True, True, True, False)
# model.def_support('N2', False, True, True, False, False, False)
model.add_node_load("N2", "FY", -10000)

renderer = Renderer(model)

# Analyze the model
model.analyze()


# Access the member stiffness matrix
member = model.members["M1"]

# Get the local stiffness matrix
local_stiffness_matrix = member.K()

# Get the transformation matrix for converting to global coordinates
transformation_matrix = member.T()

print("Displacements at nodes:")
for node_name, node in model.nodes.items():
    print(f"{node_name}: {node.DX}, {node.DY}, {node.DZ}")
