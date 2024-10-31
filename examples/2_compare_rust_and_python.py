import math
import timeit
import fers_calculations  # Ensure this is your Rust module
import numpy as np


def member_length_py(x1, y1, z1, x2, y2, z2):
    dx = x2 - x1
    dy = y2 - y1
    dz = z2 - z1
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def member_length_np(x1, y1, z1, x2, y2, z2):
    # Convert coordinates to numpy arrays
    start = np.array([x1, y1, z1])
    end = np.array([x2, y2, z2])
    # Calculate the Euclidean distance
    return np.linalg.norm(end - start)


# Set up test coordinates
coords = (0.0, 0.0, 0.0, 1.0, 1.0, 1.0)

# Measure Rust function time
rust_time = timeit.timeit(lambda: fers_calculations.member_length(*coords), number=100000)

# Measure Python function time
python_time = timeit.timeit(lambda: member_length_py(*coords), number=100000)

# Measure Numpy function time
numpy_time = timeit.timeit(lambda: member_length_np(*coords), number=100000)

# Print the results
print(f"Rust function time: {rust_time} seconds")
print(f"Python function time: {python_time} seconds")
print(f"Numpy function time: {numpy_time} seconds")
print(f"Rust is {python_time / rust_time:.2f} times faster than Python.")
print(f"Rust is {numpy_time / rust_time:.2f} times faster than Numpy.")
