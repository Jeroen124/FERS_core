from typing import Optional
from ..members.material import Material
from ..members.shapepath import ShapePath
from sectionproperties.pre.library.steel_sections import i_section, channel_section, circular_hollow_section
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
        ipe_geometry.create_mesh(mesh_sizes=[b / 1000])
        analysis_section = SP_section(ipe_geometry, time_info=False)
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

    @staticmethod
    def create_u_section(
        name: str,
        material: Material,
        h: float,
        b: float,
        t_f: float,
        t_w: float,
        r: float,
    ) -> "Section":
        """
        Static method to create a U (channel) section with uniform thickness t.
        Coordinates: z is horizontal, y is vertical. Centered on origin.
        The U is open on the right side to match ShapePath.create_u_profile.

        Parameters:
            name (str): Name of the section.
            material (Material): Material used for the section.
            h (float): Total height of the channel.
            b (float): Total width of the channel.
            t (float): Uniform thickness for web and flanges.
            r (float): Inner fillet radius at web↔flange corners.

        Returns:
            Section: A Section object representing the U profile.
        """
        # 1) Build the drawable shape path from your own path generator
        shape_commands = ShapePath.create_u_profile(h=h, b=b, t_f=t_f, t_w=t_w, r=r)
        shape_path = ShapePath(name=name, shape_commands=shape_commands)

        # 2) Build a matching sectionproperties geometry:
        #    channel_section expects separate flange/web thickness, but this U uses uniform t
        u_geometry = channel_section(d=h, b=b, t_f=t_f, t_w=t_w, r=r, n_r=16).shift_section(
            x_offset=-b / 2.0,
            y_offset=-h / 2.0,
        )

        # 3) Mesh and analyze (mesh size similar to your IPE; tweak as you like)
        u_geometry.create_mesh(mesh_sizes=[b / 1000.0])
        analysis_section = SP_section(u_geometry, time_info=False)
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

    @staticmethod
    def create_chs(
        name: str,
        material: Material,
        diameter: float,
        thickness: float,
        n: int = 64,
    ) -> "Section":
        """
        Static method to create a Circular Hollow Section (CHS).

        Parameters:
            name (str): Name of the section (e.g., "CHS 168/5/H").
            material (Material): Material used for the section.
            diameter (float): Outside diameter of the CHS (same units you use elsewhere).
            thickness (float): Wall thickness of the CHS (same units).
            n (int): Number of points used to discretize the circle (for drawing & meshing).

        Returns:
            Section: A Section object representing the CHS profile.
        """
        # Optional shape path (if you have a matching helper; otherwise we fall back to None)
        shape_path = None
        try:
            shape_commands = ShapePath.create_chs_profile(d=diameter, t=thickness, n=n)
            shape_path = ShapePath(name=name, shape_commands=shape_commands)
        except AttributeError:
            shape_path = None

        # sectionproperties geometry
        chs_geometry = circular_hollow_section(d=diameter, t=thickness, n=n).shift_section(
            x_offset=-diameter / 2.0,
            y_offset=-diameter / 2.0,
        )
        chs_geometry.create_mesh(mesh_sizes=[diameter / 1000.0])

        analysis_section = SP_section(chs_geometry, time_info=False)
        analysis_section.calculate_geometric_properties()
        analysis_section.calculate_warping_properties()

        return Section(
            name=name,
            material=material,
            i_y=float(analysis_section.section_props.iyy_c),
            i_z=float(analysis_section.section_props.ixx_c),
            j=float(analysis_section.get_j()),
            area=float(analysis_section.section_props.area),
            h=float(diameter),
            b=float(diameter),
            shape_path=shape_path,
        )

    @staticmethod
    def create_he(
        name: str,
        material: Material,
        h: float,
        b: float,
        t_f: float,
        t_w: float,
        r: float,
    ) -> "Section":
        """
        Static method to create an HE (wide-flange H) section.
        Geometry is an I/H shape with given dimensions. For series like HEA/HEB/HEM,
        pass the actual dimensions for height (h), flange width (b), flange thickness (t_f),
        web thickness (t_w) and root radius (r).

        Parameters:
            name (str): Name of the section (e.g., "HE 160 B").
            material (Material): Material used for the section.
            h (float): Total section height.
            b (float): Flange width.
            t_f (float): Flange thickness.
            t_w (float): Web thickness.
            r (float): Root fillet radius.

        Returns:
            Section: A Section object representing the HE profile.
        """
        # For drawing: an HE looks like your IPE path, so reuse if available; otherwise skip.
        shape_path = None
        try:
            shape_commands = ShapePath.create_he_profile(h=h, b=b, t_f=t_f, t_w=t_w, r=r)
        except AttributeError:
            try:
                # Fallback to IPE path generator (identical topology):
                shape_commands = ShapePath.create_ipe_profile(h=h, b=b, t_f=t_f, t_w=t_w, r=r)
            except AttributeError:
                shape_commands = None

        if shape_commands is not None:
            shape_path = ShapePath(name=name, shape_commands=shape_commands)

        # sectionproperties geometry (i_section is a generic I/H generator)
        he_geometry = i_section(d=h, b=b, t_f=t_f, t_w=t_w, r=r, n_r=16).shift_section(
            x_offset=-b / 2.0,
            y_offset=-h / 2.0,
        )
        he_geometry.create_mesh(mesh_sizes=[b / 1000.0])

        analysis_section = SP_section(he_geometry, time_info=False)
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
