import time
from PyNite import FEModel3D
from FERS_core import Node, Member, FERS, Material, Section, MemberSet, NodalSupport, NodalLoad


# =============================================================================
# Timing Utility
# =============================================================================
def time_execution(func, iterations=1, *args, **kwargs):
    """Measure execution time of a function over multiple iterations."""
    total_time = 0
    for _ in range(iterations):
        start_time = time.time()
        func(*args, **kwargs)
        end_time = time.time()
        total_time += end_time - start_time
    return total_time / iterations  # Return average time


# =============================================================================
# PyNite Setup and Calculation
# =============================================================================
def run_pynite():
    model = FEModel3D()

    # Setup PyNite model
    model.add_node("N1", 0, 0, 0)
    model.add_node("N2", 5, 5, 0)
    model.add_material("Steel", E=210e9, G=80.769e9, nu=0.3, rho=7850)
    model.add_section("IPE180", A=0.00196, Iy=0.819e-6, Iz=10.63e-6, J=0.027e-6)
    model.add_member("M1", "N1", "N2", material_name="Steel", section_name="IPE180")
    model.def_support("N1", True, True, True, True, True, True)
    model.add_node_load("N2", "FY", -1000)

    # Analyze PyNite model
    model.analyze()

    # Extract results
    displacements = {node_name: (node.DX, node.DY, node.DZ) for node_name, node in model.nodes.items()}
    return displacements


# =============================================================================
# FERS Setup and Calculation
# =============================================================================
def run_fers():
    # Setup FERS model
    calculation_1 = FERS()
    node1 = Node(0, 0, 0)
    node2 = Node(5, 0, 0)
    Steel_S235 = Material(name="Steel", e_mod=210e9, g_mod=80.769e9, density=7850, yield_stress=235e6)
    section = Section(
        name="IPE 180 Beam Section", material=Steel_S235, i_y=0.819e-6, i_z=10.63e-6, j=0.027e-6, area=0.00196
    )
    beam = Member(start_node=node1, end_node=node2, section=section)
    wall_support = NodalSupport()
    node1.nodal_support = wall_support
    membergroup1 = MemberSet(members=[beam])
    calculation_1.add_member_set(membergroup1)

    # Apply load
    end_load_case = calculation_1.create_load_case(name="End Load")
    NodalLoad(node=node2, load_case=end_load_case, magnitude=-1000, direction=(0, 1, 0))

    # Run analysis
    calculation_1.run_analysis()

    # Parse results
    return calculation_1.results


# =============================================================================
# Main Execution
# =============================================================================
if __name__ == "__main__":
    iterations = 100

    # Single-run timings
    print("Running single execution for PyNite...")
    pynite_single_time = time_execution(run_pynite)
    print(f"Single PyNite Execution Time: {pynite_single_time:.4f} seconds")

    print("\nRunning single execution for FERS...")
    fers_single_time = time_execution(run_fers)
    print(f"Single FERS Execution Time: {fers_single_time:.4f} seconds")

    # Multi-run timings (100 iterations)
    print(f"\nRunning {iterations} executions for PyNite...")
    pynite_avg_time = time_execution(run_pynite, iterations)
    print(f"Average PyNite Execution Time (100 runs): {pynite_avg_time:.4f} seconds")

    print(f"\nRunning {iterations} executions for FERS...")
    fers_avg_time = time_execution(run_fers, iterations)
    print(f"Average FERS Execution Time (100 runs): {fers_avg_time:.4f} seconds")

    # Comparison
    print("\nComparison of Execution Times:")
    print(f"Single PyNite: {pynite_single_time:.4f} seconds")
    print(f"Single FERS: {fers_single_time:.4f} seconds")
    print(f"Average PyNite (100 runs): {pynite_avg_time:.4f} seconds")
    print(f"Average FERS (100 runs): {fers_avg_time:.4f} seconds")
    if pynite_single_time < fers_single_time:
        print("Single-run: PyNite is faster.")
    else:
        print("Single-run: FERS is faster.")

    if pynite_avg_time < fers_avg_time:
        print("100-run: PyNite is faster.")
    else:
        print("100-run: FERS is faster.")
