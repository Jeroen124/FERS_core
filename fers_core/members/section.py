from typing import Optional
from ..members.material import Material
from ..members.shapepath import ShapePath
from sectionproperties.pre.library.steel_sections import i_section
from sectionproperties.analysis.section import Section as SP_section

import matplotlib.pyplot as plt


class Section:
    _section_counter = 1

    def __init__(
        self,
        name: str,
        material: Material,
        i_y: float,
        i_z: float,
        j: float,
        area: float,
        h: Optional[float] = None,
        b: Optional[float] = None,
        id: Optional[int] = None,
        shape_path: Optional[ShapePath] = None,
    ):
        """
        Initializes a Section object representing a structural element.
        Parameters:
        id (int, optional): Unique identifier for the section.
        name (str): Descriptive name of the section.
        material (Material): Material object representing the type of material used (e.g., steel).
        i_y (float): Second moment of area about the y-axis, indicating resistance to bending.
        i_z (float): Second moment of area about the z-axis, indicating resistance to bending.
        j (float): St Venant Torsional constant, indicating resistance to torsion.
        area (float): Cross-sectional area of the section, relevant for load calculations.
        h (float, optional): Height of the section, if applicable.
        b (float, optional): Width of the section, if applicable.
        t_w (float, optional): Thickness of the web, if applicable (default is None).
        t_f (float, optional): Thickness of the flange, if applicable (default is None).
        """
        self.id = id or Section._section_counter
        if id is None:
            Section._section_counter += 1
        self.name = name
        self.material = material
        self.h = h
        self.b = b
        self.i_y = i_y
        self.i_z = i_z
        self.j = j
        self.area = area
        self.shape_path = shape_path

    @classmethod
    def reset_counter(cls):
        cls._section_counter = 1

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "material": self.material.id,
            "h": self.h,
            "b": self.b,
            "i_y": self.i_y,
            "i_z": self.i_z,
            "j": self.j,
            "area": self.area,
            "shape_path": self.shape_path.id if self.shape_path else None,
        }

    @staticmethod
    def create_ipe_section(
        name: str,
        material: Material,
        h: float,
        b: float,
        t_f: float,
        t_w: float,
        r: float,
    ) -> "Section":
        """
        Static method to create an IPE section.
        Parameters:
        name (str): Name of the section.
        material (Material): Material used for the section.
        h (float): Total height of the IPE section.
        b (float): Flange width.
        t_f (float): Flange thickness.
        t_w (float): Web thickness.
        r (float): Fillet radius.
        Returns:
        Section: A Section object representing the IPE profile.
        """
        shape_commands = ShapePath.create_ipe_profile(h, b, t_f, t_w, r)
        shape_path = ShapePath(name=name, shape_commands=shape_commands)

        # Use the sectionproperties module to compute section properties
        ipe_geometry = i_section(d=h, b=b, t_f=t_f, t_w=t_w, r=r, n_r=16).shift_section(
            x_offset=-b / 2, y_offset=-h / 2
        )
        mesh = ipe_geometry.create_mesh(mesh_sizes=[b / 1000])
        analysis_section = SP_section(ipe_geometry, mesh)
        analysis_section.calculate_geometric_properties()
        analysis_section.calculate_warping_properties()

        return Section(
            name=name,
            material=material,
            i_y=float(analysis_section.section_props.iyy_c),
            i_z=float(analysis_section.section_props.ixx_c),
            j=float(analysis_section.get_j()),
            area=float(analysis_section.section_props.area),
            h=h,
            b=b,
            shape_path=shape_path,
        )

    def plot(self, show_nodes: bool = True):
        """
        Plots the cross-section of the section.
        - If `shape_path` is defined, it delegates the plot to `shape_path.plot`.
        - Otherwise, it plots a placeholder message.

        Parameters:
        show_nodes (bool): Whether to display node numbers if shape_path is used. Default is True.
        """
        if self.shape_path:
            self.shape_path.plot(show_nodes=show_nodes)
        else:
            print(f"No shape_path defined for Section: {self.name}. Plotting not available.")
            plt.figure()
            plt.text(0.5, 0.5, "No Shape Defined", fontsize=20, ha="center", va="center")
            plt.title(f"Section: {self.name}")
            plt.axis("off")
            plt.show()
