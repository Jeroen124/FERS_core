"""
803 — DXF Cross-Section Import
===============================
Demonstrates how to import a cross-section outline from a DXF file
and use it in a FERS analysis.

The ShapePath.from_dxf() method reads LINE, LWPOLYLINE, ARC and
CIRCLE entities from a .dxf file (requires the `ezdxf` package).

    pip install ezdxf

Key features shown:
  • ShapePath.from_dxf(filepath, name, layer)
  • Using a DXF-imported ShapePath as the cross-section geometry
  • Computing section properties via sectionproperties
  • Plotting the imported cross-section
"""

import os
from fers_core import ShapePath, Section, Material


# =============================================================================
# Step 1: Material
# =============================================================================
steel = Material(name="S355", e_mod=210e9, g_mod=81e9, density=7850, yield_stress=355e6)


# =============================================================================
# Step 2: Import a cross-section from DXF
# =============================================================================
# Point this to your own DXF file containing a closed cross-section outline.
# The DXF should be drawn in mm (X → ShapePath z-axis, Y → ShapePath y-axis).
#
# If you do not have a DXF file handy, the code below shows the workflow
# and will print a helpful error if the file is missing.

dxf_path = os.path.join(os.path.dirname(__file__), "sample_section.dxf")

if os.path.isfile(dxf_path):
    # --- Import from file ---
    shape = ShapePath.from_dxf(
        filepath=dxf_path,
        name="DXF Section",
        layer=None,  # set a layer name to filter, or None for all
    )

    print(f"Imported ShapePath '{shape.name}' with {len(shape.shape_commands)} commands")

    # Optional: visualise what was imported
    # shape.plot()

    # --- Compute section properties and create a Section ---
    # For a DXF-imported shape you will need to provide section properties
    # either manually or via sectionproperties.  Here is the manual route:
    section_dxf = Section(
        name="DXF Section",
        material=steel,
        i_y=1.0e-6,  # replace with actual value
        i_z=1.0e-6,  # replace with actual value
        j=1.0e-6,  # replace with actual value
        area=1.0e-3,  # replace with actual value
        shape_path=shape,
    )
    print(f"Section created: {section_dxf.name}")

    # You can also compute the section properties from the geometry
    # using sectionproperties:
    #
    #   geometry = shape.get_shape_geometry()
    #   geometry.create_mesh(mesh_sizes=[0.001])
    #   from sectionproperties.analysis.section import Section as SP_section
    #   analysis = SP_section(geometry, time_info=False)
    #   analysis.calculate_geometric_properties()
    #   analysis.calculate_warping_properties()
    #   print(f"Area = {analysis.section_props.area}")
    #   print(f"I_yy = {analysis.section_props.iyy_c}")
    #   print(f"I_xx = {analysis.section_props.ixx_c}")
    #   print(f"J    = {analysis.get_j()}")

else:
    print(f"DXF file not found: {dxf_path}")
    print()
    print("To try this example, create a DXF file with a closed cross-section")
    print("outline and place it next to this script as 'sample_section.dxf'.")
    print()
    print("Supported DXF entities: LINE, LWPOLYLINE (with bulge arcs), ARC, CIRCLE.")
    print()
    print("--- Showing the from_dxf API signature instead ---")
    help(ShapePath.from_dxf)
