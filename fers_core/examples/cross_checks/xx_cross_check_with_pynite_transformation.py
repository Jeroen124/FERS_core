import numpy as np

# Define start and end nodes as dictionaries
start_node = {"X": 0.0, "Y": 0.0, "Z": 0.0}
end_node = {"X": 5.0, "Y": 5.0, "Z": 0.0}

# Compute the local x-axis (direction vector from start_node to end_node)
dx = end_node["X"] - start_node["X"]
dy = end_node["Y"] - start_node["Y"]
dz = end_node["Z"] - start_node["Z"]
length = np.sqrt(dx**2 + dy**2 + dz**2)

if length < 1e-12:
    raise ValueError("Start and end nodes are the same or too close to define a direction.")

local_x = np.array([dx / length, dy / length, dz / length])

# Define the primary reference vector (global Y-axis)
start_node_array = np.array([start_node["X"], start_node["Y"], start_node["Z"]])
primary_ref = np.array([0, 1, 0]) + start_node_array

# Check if local_x is parallel or nearly parallel to the primary reference vector
dot_product = np.dot(local_x, primary_ref)
if np.abs(dot_product) > 1.0 - 1e-6:
    # If parallel, choose an alternative reference vector (global Z-axis)
    reference_vector = np.array([0, 0, 1]) + start_node_array
else:
    # Otherwise, use the primary reference vector
    reference_vector = primary_ref

# Compute the local z-axis as the cross product of local_x and reference_vector
local_z = np.cross(local_x, reference_vector)
norm_z = np.linalg.norm(local_z)
if norm_z < 1e-12:
    # If the cross product is near zero, choose a different reference vector
    reference_vector = np.array([1, 0, 0]) + start_node_array
    local_z = np.cross(local_x, reference_vector)
    norm_z = np.linalg.norm(local_z)
    if norm_z < 1e-12:
        raise ValueError(
            "Cannot define a valid local_z axis; local_x is collinear with all reference vectors."
        )

local_z /= norm_z

# Compute the local y-axis as the cross product of local_z and local_x
local_y = np.cross(local_z, local_x)
norm_y = np.linalg.norm(local_y)
if norm_y < 1e-12:
    raise ValueError("Cannot define local_y axis; local_z and local_x are collinear.")

local_y /= norm_y

# Print the results for debugging
print("Local X-axis:", local_x)
print("Local Y-axis:", local_y)
print("Local Z-axis:", local_z)

x1 = start_node["X"]
y1 = start_node["Y"]
z1 = start_node["Z"]

x2 = end_node["X"]
y2 = end_node["Y"]
z2 = end_node["Z"]

L = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2 + (z2 - z1) ** 2)
x = [(x2 - x1) / L, (y2 - y1) / L, (z2 - z1) / L]

proj = [x2 - x1, 0, z2 - z1]

# Find a vector in the direction of the local z-axis by taking the cross-product
# of the local x-axis and its projection on a plane parallel to the XZ plane. This
# produces a vector perpendicular to both the local x-axis and its projection. This
# vector will always be horizontal since it's parallel to the XZ plane. The order
# in which the vectors are 'crossed' has been selected to ensure the y-axis always
# has an upward component (i.e. the top of the beam is always on top).
if y2 > y1:
    z = np.cross(proj, x)
else:
    z = np.cross(x, proj)

# Divide the z-vector by its magnitude to produce a unit vector of direction cosines
z = np.divide(z, (z[0] ** 2 + z[1] ** 2 + z[2] ** 2) ** 0.5)

# Find the direction cosines for the local y-axis
y = np.cross(z, x)
y = np.divide(y, (y[0] ** 2 + y[1] ** 2 + y[2] ** 2) ** 0.5)


dirCos = np.array([x, y, z])
