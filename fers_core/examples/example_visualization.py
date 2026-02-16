"""Example demonstrating the new modular visualization architecture.

This example shows how to use FERS with the modular renderer system where
each class (Node, Member, etc.) defines its own render() method, and the
model uses top-level renderers accessed via get_model_renderer() and
get_result_renderer().
"""

from fers_core.fers.fers import FERS
from fers_core.nodes.node import Node
from fers_core.members.member import Member
from fers_core.members.memberset import MemberSet
from fers_core.members.section import Section
from fers_core.members.material import Material
from fers_core.supports.nodalsupport import NodalSupport


def create_simple_model() -> FERS:
    """Create a simple cantilever beam model."""
    # Create FERS instance
    model = FERS()

    # Create material
    material = Material(
        name="Steel",
        e_mod=210000.0,  # MPa
        density=7850e-9,  # kg/mm³
        poisson=0.3,
    )

    # Create section
    section = Section(
        name="HEB200",
        material=material,
        area=7808.0,  # mm²
        i_y=5696e4,  # mm⁴
        i_z=2003e4,  # mm⁴
        w_y=569600.0,  # mm³
        w_z=200300.0,  # mm³
    )

    # Create support
    fixed_support = NodalSupport(Tx=True, Ty=True, Tz=True, Rx=True, Ry=True, Rz=True, name="Fixed")

    # Create nodes
    node1 = Node(X=0.0, Y=0.0, Z=0.0, nodal_support=fixed_support)
    node2 = Node(X=3000.0, Y=0.0, Z=0.0)
    node3 = Node(X=6000.0, Y=0.0, Z=0.0)

    # Create members
    member1 = Member(start_node=node1, end_node=node2, section=section)
    member2 = Member(start_node=node2, end_node=node3, section=section)

    # Create member set and add to model
    member_set = MemberSet(members=[member1, member2])
    model.add_member_set(member_set)

    return model


def main():
    """Main function to demonstrate modular visualization."""
    # Create model
    model = create_simple_model()

    # ===== Model Visualization =====
    print("Creating model renderer...")
    model_renderer = model.get_model_renderer()

    # Configure rendering options
    model_renderer.render_nodes = True
    model_renderer.render_supports = True
    model_renderer.labels = True

    # Save screenshot
    model_renderer.screenshot("cantilever_model.png")
    print("Model screenshot saved as 'cantilever_model.png'")

    # Show interactive view (if not in off-screen mode)
    # model_renderer.show()

    # Clean up
    model_renderer.close()

    # ===== Result Visualization =====
    # After running analysis, you can use the result renderer
    # model.run_analysis()

    # print("Creating result renderer...")
    # result_renderer = model.get_result_renderer()

    # result_renderer.deformed_shape = True
    # result_renderer.deformed_scale = 50.0
    # result_renderer.member_diagrams = 'My'
    # result_renderer.diagram_scale = 30.0

    # result_renderer.screenshot("cantilever_results.png")
    # print("Result screenshot saved as 'cantilever_results.png'")

    # result_renderer.close()

    print("\nNote: Each Node and Member has its own render() method.")
    print("The renderers call these methods to build the visualization.")


if __name__ == "__main__":
    main()
