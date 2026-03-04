from typing import Optional
from ..members.material import Material
from ..members.shapepath import ShapePath
from sectionproperties.pre.library.steel_sections import (
    i_section,
    channel_section,
    circular_hollow_section,
    rectangular_hollow_section,
    angle_section,
    cee_section,
    zed_section,
)
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

    @classmethod
    def from_dict(
        cls,
        data: dict,
        materials_by_id: dict[int, Material],
        shapepaths_by_id: dict[int, "ShapePath"],
    ) -> "Section":
        material_id = data.get("material")
        material = materials_by_id[material_id] if material_id is not None else None

        shape_path_id = data.get("shape_path")
        shape_path = shapepaths_by_id.get(shape_path_id) if shape_path_id is not None else None

        return cls(
            id=data.get("id"),
            name=data["name"],
            material=material,
            h=data.get("h"),
            b=data.get("b"),
            i_y=data["i_y"],
            i_z=data["i_z"],
            j=data["j"],
            area=data["area"],
            shape_path=shape_path,
        )

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

    @staticmethod
    def create_rhs(
        name: str,
        material: Material,
        h: float,
        b: float,
        t: float,
        r_out: float = 0.0,
    ) -> "Section":
        """
        Create a Rectangular Hollow Section (RHS). Also suitable for SHS when h == b.

        Parameters:
            name: Name of the section (e.g., "RHS 200x100x6").
            material: Material used for the section.
            h: Total height.
            b: Total width.
            t: Wall thickness.
            r_out: Outer corner radius (0 for sharp corners).

        Returns:
            Section: A Section object representing the RHS profile.
        """
        shape_commands = ShapePath.create_rhs_profile(h=h, b=b, t=t, r_out=r_out)
        shape_path = ShapePath(name=name, shape_commands=shape_commands)

        rhs_geometry = rectangular_hollow_section(
            d=h,
            b=b,
            t=t,
            r_out=r_out,
            n_r=16,
        ).shift_section(x_offset=-b / 2.0, y_offset=-h / 2.0)
        rhs_geometry.create_mesh(mesh_sizes=[max(b, h) / 1000.0])

        analysis_section = SP_section(rhs_geometry, time_info=False)
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
    def create_shs(
        name: str,
        material: Material,
        b: float,
        t: float,
        r_out: float = 0.0,
    ) -> "Section":
        """
        Create a Square Hollow Section (SHS). Convenience wrapper around create_rhs.

        Parameters:
            name: Name of the section (e.g., "SHS 100x100x6").
            material: Material used for the section.
            b: Side length.
            t: Wall thickness.
            r_out: Outer corner radius.

        Returns:
            Section: A Section object representing the SHS profile.
        """
        return Section.create_rhs(name=name, material=material, h=b, b=b, t=t, r_out=r_out)

    @staticmethod
    def create_angle_section(
        name: str,
        material: Material,
        h: float,
        b: float,
        t: float,
        r_root: float = 0.0,
        r_toe: float = 0.0,
    ) -> "Section":
        """
        Create an angle (L) section.

        Parameters:
            name: Name of the section (e.g., "L 100x100x10").
            material: Material used for the section.
            h: Height of the vertical leg.
            b: Width of the horizontal leg.
            t: Uniform thickness.
            r_root: Root radius at the inner corner.
            r_toe: Toe radius at tips.

        Returns:
            Section: A Section object representing the angle profile.
        """
        shape_commands = ShapePath.create_angle_profile(
            h=h,
            b=b,
            t=t,
            r_root=r_root,
            r_toe=r_toe,
        )
        shape_path = ShapePath(name=name, shape_commands=shape_commands)

        # sectionproperties places the angle with bottom-left at origin;
        # we shift to center on centroid.
        angle_geometry = angle_section(
            d=h,
            b=b,
            t=t,
            r_r=r_root,
            r_t=r_toe,
            n_r=16,
        )
        # Compute centroid first, then shift
        angle_geometry.create_mesh(mesh_sizes=[max(h, b) / 1000.0])
        analysis_section = SP_section(angle_geometry, time_info=False)
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
    def create_welded_i_section(
        name: str,
        material: Material,
        h: float,
        b: float,
        t_f: float,
        t_w: float,
    ) -> "Section":
        """
        Create a welded I-section (no root radius). Built from plates.

        Parameters:
            name: Name of the section (e.g., "Welded I 500x200x10x16").
            material: Material used for the section.
            h: Total height.
            b: Flange width.
            t_f: Flange thickness.
            t_w: Web thickness.

        Returns:
            Section: A Section object representing the welded I profile.
        """
        shape_commands = ShapePath.create_welded_i_profile(
            h=h,
            b=b,
            t_f=t_f,
            t_w=t_w,
        )
        shape_path = ShapePath(name=name, shape_commands=shape_commands)

        welded_geometry = i_section(
            d=h,
            b=b,
            t_f=t_f,
            t_w=t_w,
            r=0.0,
            n_r=1,
        ).shift_section(x_offset=-b / 2.0, y_offset=-h / 2.0)
        welded_geometry.create_mesh(mesh_sizes=[b / 1000.0])

        analysis_section = SP_section(welded_geometry, time_info=False)
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
    def create_cfs_c(
        name: str,
        material: Material,
        h: float,
        b: float,
        lip: float,
        t: float,
        r_out: float = 0.0,
    ) -> "Section":
        """
        Create a cold-formed steel C-section (lipped channel).

        Parameters:
            name: Name of the section (e.g., "C 200x75x20x2.0").
            material: Material used for the section.
            h: Total depth.
            b: Flange width.
            lip: Lip length (0 for unlipped).
            t: Wall thickness.
            r_out: Outer bend radius.

        Returns:
            Section: A Section object representing the cold-formed C profile.
        """
        shape_commands = ShapePath.create_cfs_c_profile(
            h=h,
            b=b,
            lip=lip,
            t=t,
            r_out=r_out,
        )
        shape_path = ShapePath(name=name, shape_commands=shape_commands)

        cfs_geometry = cee_section(
            d=h,
            b=b,
            l=lip,
            t=t,
            r_out=r_out,
            n_r=16,
        ).shift_section(x_offset=-b / 2.0, y_offset=-h / 2.0)
        cfs_geometry.create_mesh(mesh_sizes=[max(h, b) / 1000.0])

        analysis_section = SP_section(cfs_geometry, time_info=False)
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
    def create_cfs_z(
        name: str,
        material: Material,
        h: float,
        b_top: float,
        b_bot: float,
        lip: float,
        t: float,
        r_out: float = 0.0,
    ) -> "Section":
        """
        Create a cold-formed steel Z-section (lipped zed).

        Parameters:
            name: Name of the section (e.g., "Z 200x75x75x20x2.0").
            material: Material used for the section.
            h: Total depth.
            b_top: Top flange width.
            b_bot: Bottom flange width.
            lip: Lip length (0 for unlipped).
            t: Wall thickness.
            r_out: Outer bend radius.

        Returns:
            Section: A Section object representing the cold-formed Z profile.
        """
        shape_commands = ShapePath.create_cfs_z_profile(
            h=h,
            b_top=b_top,
            b_bot=b_bot,
            lip=lip,
            t=t,
            r_out=r_out,
        )
        shape_path = ShapePath(name=name, shape_commands=shape_commands)

        zed_geometry = zed_section(
            d=h,
            b_l=b_bot,
            b_r=b_top,
            l=lip,
            t=t,
            r_out=r_out,
            n_r=16,
        ).shift_section(x_offset=-max(b_top, b_bot) / 2.0, y_offset=-h / 2.0)
        zed_geometry.create_mesh(mesh_sizes=[max(h, b_top, b_bot) / 1000.0])

        analysis_section = SP_section(zed_geometry, time_info=False)
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
            b=max(b_top, b_bot),
            shape_path=shape_path,
        )

    @staticmethod
    def from_name(name: str, material: Material) -> "Section":
        """
        Create a standard section by name from the built-in library.

        Supports European steel profiles per EN 10365 and common hollow sections.

        Examples:
            Section.from_name("IPE200", steel)
            Section.from_name("HEA160", steel)
            Section.from_name("HEB300", steel)
            Section.from_name("RHS 200x100x6", steel)
            Section.from_name("SHS 100x100x6", steel)
            Section.from_name("L 100x100x10", steel)
            Section.from_name("CHS 168.3x5", steel)
            Section.from_name("UPE200", steel)

        Parameters:
            name: Standard section designation.
            material: Material object.

        Returns:
            Section: Fully constructed section with geometry and properties.

        Raises:
            ValueError: If the profile name is not found in the library.
        """
        from ..sections.steel_sections_en import resolve_section

        return resolve_section(name, material)

    @staticmethod
    def list_available(series: Optional[str] = None) -> list:
        """
        List available section names in the built-in library.

        Parameters:
            series: Optional filter, e.g. "IPE", "HEA", "RHS", "SHS", "L", "CHS", "UPE".
                    If None, returns all available sections.

        Returns:
            List of section name strings.
        """
        from ..sections.steel_sections_en import list_sections

        return list_sections(series)
