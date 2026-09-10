from typing import Any, Dict, Optional
from ..members.material import Material
from ..members.shapepath import ShapePath
from .ec3_section import section_ec3

try:
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
except ImportError:  # pragma: no cover - optional dependency for section generators
    i_section = None
    channel_section = None
    circular_hollow_section = None
    rectangular_hollow_section = None
    angle_section = None
    cee_section = None
    zed_section = None
    SP_section = None

import matplotlib.pyplot as plt


def _require_sectionproperties() -> None:
    if SP_section is None:
        raise ImportError(
            "sectionproperties is required for generated section geometry. "
            "Install the FERS_core section-generation dependencies to use these helpers."
        )


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
        i_w: Optional[float] = None,
        y_s: Optional[float] = None,
        z_s: Optional[float] = None,
        wagner_coeff: Optional[float] = None,
        a_sy: Optional[float] = None,
        a_sz: Optional[float] = None,
        wel_y: Optional[float] = None,
        wel_z: Optional[float] = None,
        wpl_y: Optional[float] = None,
        wpl_z: Optional[float] = None,
        principal_axis_angle: Optional[float] = None,
        i_yz: Optional[float] = None,
        centroid_y: Optional[float] = None,
        centroid_z: Optional[float] = None,
        ec3: Optional[Dict[str, Any]] = None,
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
        i_w (float, optional): Warping constant (m^6), for thin-walled open sections.
        y_s (float, optional): Shear center Y-coordinate relative to centroid (m).
        z_s (float, optional): Shear center Z-coordinate relative to centroid (m).
        wagner_coeff (float, optional): Wagner coefficient for lateral-torsional buckling.
        a_sy (float, optional): Effective shear area in Y-direction (m^2) for Timoshenko beam.
        a_sz (float, optional): Effective shear area in Z-direction (m^2) for Timoshenko beam.
        principal_axis_angle (float, optional): Angle (degrees) from centroidal to principal
            axes.  When i_y/i_z are principal MOIs and the section has non-zero Iyz,
            this rotates the member's local y-z axes to align with principal directions.
        i_yz (float, optional): Product of inertia about centroidal axes (mm^4).
        centroid_y (float, optional): Centroid Y-coordinate in shape path coords (mm).
        centroid_z (float, optional): Centroid Z-coordinate in shape path coords (mm).
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
        self.i_w = i_w
        self.y_s = y_s
        self.z_s = z_s
        self.wagner_coeff = wagner_coeff
        self.a_sy = a_sy
        self.a_sz = a_sz
        self.wel_y = wel_y
        self.wel_z = wel_z
        self.wpl_y = wpl_y
        self.wpl_z = wpl_z
        self.principal_axis_angle = principal_axis_angle
        self.i_yz = i_yz
        # EN 1993-1-1 design parameters (section class, buckling curves,
        # effective properties), shaped like the solver's `Section.ec3` block.
        # The factories fill this from the profile's own dimensions via
        # `fers_core.members.ec3_section`; a hand-built Section can pass it
        # directly. Without it the solver defaults every buckling curve to b and
        # infers class 1 from the presence of `wpl_y`, which is wrong for a
        # channel (curve c) and unsafe for anything class 4.
        self.ec3 = ec3
        self.centroid_y = centroid_y
        self.centroid_z = centroid_z

    @classmethod
    def reset_counter(cls):
        cls._section_counter = 1

    @staticmethod
    def _extract_advanced_props(analysis_section) -> dict:
        """Extract warping and shear properties from a sectionproperties analysis section.

        Returns a dict with keys: i_w, y_s, z_s, wagner_coeff, a_sy, a_sz.
        Any property that cannot be computed returns None.
        """
        props = {}
        sp = analysis_section.section_props
        try:
            props["i_w"] = float(sp.gamma)
        except (AttributeError, TypeError):
            props["i_w"] = None
        # Axis mapping. Every factory stores i_y = sp.iyy_c and i_z = sp.ixx_c.
        # i_y is the second moment ABOUT local y, i.e. int(z^2 dA); iyy_c is
        # int(x^2 dA). So FERS local z is the sectionproperties x direction and
        # FERS local y is the sectionproperties y direction, and the shear-centre
        # coordinates have to follow that same mapping.
        #
        # These were crossed. It is not cosmetic: the solver reads y_s/z_s for
        # the EN 1993-1-1 6.3.1.4 torsional-flexural cubic, where an offset along
        # one axis couples torsion with the flexural mode that deflects along the
        # OTHER one. Crossing them coupled torsion with the wrong mode for every
        # mono-symmetric section - channels, tees, angles. A plain 80x50x3
        # channel has its shear centre 32.3 mm out along local z with nothing on
        # local y, and was stored the other way round.
        try:
            props["y_s"] = float(sp.y_se)
            props["z_s"] = float(sp.x_se)
        except (AttributeError, TypeError):
            props["y_s"] = None
            props["z_s"] = None
        # Wagner coefficient: polar radius of gyration about shear center squared
        # ip_s² = (Iy + Iz)/A + ys² + zs²
        try:
            iy = float(sp.iyy_c)
            iz = float(sp.ixx_c)
            area = float(sp.area)
            ys = props["y_s"] or 0.0
            zs = props["z_s"] or 0.0
            props["wagner_coeff"] = (iy + iz) / area + ys**2 + zs**2
        except (AttributeError, TypeError, ZeroDivisionError):
            props["wagner_coeff"] = None
        try:
            as_tuple = analysis_section.get_as()
            props["a_sy"] = float(as_tuple[0])
            props["a_sz"] = float(as_tuple[1])
        except (AttributeError, TypeError, IndexError):
            props["a_sy"] = None
            props["a_sz"] = None
        # Product of inertia about the centroidal axes. Under the factories'
        # mapping (i_y = iyy_c, i_z = ixx_c, so FERS y is the sectionproperties y
        # direction and FERS z its x), I_yz = int(y*z dA) is exactly ixy_c.
        try:
            ixy_c = float(sp.ixy_c)
            props["i_yz"] = ixy_c if abs(ixy_c) > 1e-10 else None
        except (AttributeError, TypeError):
            ixy_c = None
            props["i_yz"] = None

        # Principal axis angle, in degrees.
        #
        # Derived here rather than read from sp.phi, for two reasons. sp.phi is
        # already in DEGREES (an angle section reports -135.0), so the old
        # math.degrees() call turned it into -7734.9. And even unconverted it
        # would not do: the solver decides whether i_y/i_z are centroidal by
        # checking this angle against its own Mohr angle
        # theta = 0.5*atan2(-2*I_yz, I_y - I_z), which for that same angle is
        # +45 deg. -135 names the same axis but fails the comparison, so the
        # rotation is skipped and the CENTROIDAL pair is used as if it were
        # principal - for an L 100x100x10 that is 177 cm4 in place of 73 cm4,
        # a factor 2.4 on N_cr in the unconservative direction.
        #
        # Computing it from the same two quantities the solver compares against
        # makes the match true by construction.
        try:
            import math

            if ixy_c is None or props["i_yz"] is None:
                props["principal_axis_angle"] = None
            else:
                i_y = float(sp.iyy_c)
                i_z = float(sp.ixx_c)
                theta = 0.5 * math.atan2(-2.0 * ixy_c, i_y - i_z)
                props["principal_axis_angle"] = math.degrees(theta)
        except (AttributeError, TypeError):
            props["principal_axis_angle"] = None
        # Centroid coordinates within the shape path coordinate system.
        #
        # KNOWN: these are crossed the same way y_s/z_s were (cx belongs on
        # centroid_z under the mapping above). Deliberately NOT corrected here.
        # Unlike y_s/z_s the solver never reads them - they only offset the
        # viewer's shape-path extrusion - so flipping them silently moves
        # rendered geometry for every mono-symmetric section, which needs its own
        # visual verification rather than riding along with a capacity fix.
        # FERS_cloud already compensates: see the note in src/data/sectionFixtures.ts.
        try:
            props["centroid_y"] = float(sp.cx)
            props["centroid_z"] = float(sp.cy)
        except (AttributeError, TypeError):
            props["centroid_y"] = None
            props["centroid_z"] = None
        # Elastic + plastic section moduli. sectionproperties xx maps to FERS i_z
        # (i_z = ixx_c) and yy to FERS i_y, so wel_z/wpl_z are the strong-axis
        # (major) moduli for I-sections. Plastic moduli need an extra analysis pass.
        try:
            analysis_section.calculate_plastic_properties()
        except Exception:  # noqa: BLE001 - plastic props are optional
            pass
        try:
            z = analysis_section.get_z()  # (zxx+, zxx-, zyy+, zyy-)
            props["wel_z"] = min(abs(float(z[0])), abs(float(z[1])))
            props["wel_y"] = min(abs(float(z[2])), abs(float(z[3])))
        except (AttributeError, TypeError, IndexError, ValueError):
            props["wel_z"] = None
            props["wel_y"] = None
        try:
            s = analysis_section.get_s()  # (sxx, syy) plastic moduli
            props["wpl_z"] = float(s[0])
            props["wpl_y"] = float(s[1])
        except (AttributeError, TypeError, IndexError, ValueError):
            props["wpl_z"] = None
            props["wpl_y"] = None
        return props

    def to_dict(self):
        d = {
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
        if self.i_w is not None:
            d["i_w"] = self.i_w
        if self.y_s is not None:
            d["y_s"] = self.y_s
        if self.z_s is not None:
            d["z_s"] = self.z_s
        if self.wagner_coeff is not None:
            d["wagner_coeff"] = self.wagner_coeff
        if self.a_sy is not None:
            d["a_sy"] = self.a_sy
        if self.a_sz is not None:
            d["a_sz"] = self.a_sz
        if self.wel_y is not None:
            d["wel_y"] = self.wel_y
        if self.wel_z is not None:
            d["wel_z"] = self.wel_z
        if self.wpl_y is not None:
            d["wpl_y"] = self.wpl_y
        if self.wpl_z is not None:
            d["wpl_z"] = self.wpl_z
        if self.principal_axis_angle is not None:
            d["principal_axis_angle"] = self.principal_axis_angle
        if self.i_yz is not None:
            d["i_yz"] = self.i_yz
        if self.centroid_y is not None:
            d["centroid_y"] = self.centroid_y
        if self.centroid_z is not None:
            d["centroid_z"] = self.centroid_z
        if self.ec3:
            d["ec3"] = dict(self.ec3)
        return d

    @classmethod
    def from_dict(
        cls,
        data: dict,
        materials_by_id: dict[int, Material],
        shapepaths_by_id: dict[int, "ShapePath"],
        classify_for: Optional[str] = None,
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
            i_w=data.get("i_w"),
            y_s=data.get("y_s"),
            z_s=data.get("z_s"),
            wagner_coeff=data.get("wagner_coeff"),
            a_sy=data.get("a_sy"),
            a_sz=data.get("a_sz"),
            wel_y=data.get("wel_y"),
            wel_z=data.get("wel_z"),
            wpl_y=data.get("wpl_y"),
            wpl_z=data.get("wpl_z"),
            principal_axis_angle=data.get("principal_axis_angle"),
            i_yz=data.get("i_yz"),
            centroid_y=data.get("centroid_y"),
            centroid_z=data.get("centroid_z"),
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
        classify_for: Optional[str] = None,
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
        adv = Section._extract_advanced_props(analysis_section)

        _area = float(analysis_section.section_props.area)
        _ec3, _ = section_ec3(
            "i",
            material.yield_stress,
            _area,
            fabrication="hot_rolled",
            h=h,
            b=b,
            t_f=t_f,
            t_w=t_w,
            r=r,
            classify_for=classify_for,
        )

        return Section(
            name=name,
            material=material,
            i_y=float(analysis_section.section_props.iyy_c),
            i_z=float(analysis_section.section_props.ixx_c),
            j=float(analysis_section.get_j()),
            area=_area,
            h=h,
            b=b,
            shape_path=shape_path,
            ec3=_ec3,
            **adv,
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
        fabrication: str = "hot_rolled",
        classify_for: Optional[str] = None,
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
        adv = Section._extract_advanced_props(analysis_section)

        _area = float(analysis_section.section_props.area)
        _ec3, _ = section_ec3(
            "channel",
            material.yield_stress,
            _area,
            fabrication=fabrication,
            h=h,
            b=b,
            t_f=t_f,
            t_w=t_w,
            r=r,
            classify_for=classify_for,
        )

        return Section(
            name=name,
            material=material,
            i_y=float(analysis_section.section_props.iyy_c),
            i_z=float(analysis_section.section_props.ixx_c),
            j=float(analysis_section.get_j()),
            area=_area,
            h=h,
            b=b,
            shape_path=shape_path,
            ec3=_ec3,
            **adv,
        )

    @staticmethod
    def create_chs(
        name: str,
        material: Material,
        diameter: float,
        thickness: float,
        n: int = 64,
        fabrication: str = "hot_finished",
        classify_for: Optional[str] = None,
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
        adv = Section._extract_advanced_props(analysis_section)

        _area = float(analysis_section.section_props.area)
        _ec3, _ = section_ec3(
            "chs",
            material.yield_stress,
            _area,
            fabrication=fabrication,
            d=diameter,
            t=thickness,
            classify_for=classify_for,
        )

        return Section(
            name=name,
            material=material,
            i_y=float(analysis_section.section_props.iyy_c),
            i_z=float(analysis_section.section_props.ixx_c),
            j=float(analysis_section.get_j()),
            area=_area,
            h=float(diameter),
            b=float(diameter),
            shape_path=shape_path,
            ec3=_ec3,
            **adv,
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
        classify_for: Optional[str] = None,
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
        adv = Section._extract_advanced_props(analysis_section)

        _area = float(analysis_section.section_props.area)
        _ec3, _ = section_ec3(
            "i",
            material.yield_stress,
            _area,
            fabrication="hot_rolled",
            h=h,
            b=b,
            t_f=t_f,
            t_w=t_w,
            r=r,
            classify_for=classify_for,
        )

        return Section(
            name=name,
            material=material,
            i_y=float(analysis_section.section_props.iyy_c),
            i_z=float(analysis_section.section_props.ixx_c),
            j=float(analysis_section.get_j()),
            area=_area,
            h=h,
            b=b,
            shape_path=shape_path,
            ec3=_ec3,
            **adv,
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
        fabrication: str = "hot_finished",
        classify_for: Optional[str] = None,
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
        adv = Section._extract_advanced_props(analysis_section)

        _area = float(analysis_section.section_props.area)
        _ec3, _ = section_ec3(
            "rhs",
            material.yield_stress,
            _area,
            fabrication=fabrication,
            h=h,
            b=b,
            t=t,
            r=r_out,
            classify_for=classify_for,
        )

        return Section(
            name=name,
            material=material,
            i_y=float(analysis_section.section_props.iyy_c),
            i_z=float(analysis_section.section_props.ixx_c),
            j=float(analysis_section.get_j()),
            area=_area,
            h=h,
            b=b,
            shape_path=shape_path,
            ec3=_ec3,
            **adv,
        )

    @staticmethod
    def create_shs(
        name: str,
        material: Material,
        b: float,
        t: float,
        r_out: float = 0.0,
        fabrication: str = "hot_finished",
        classify_for: Optional[str] = None,
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
        return Section.create_rhs(
            name=name,
            material=material,
            h=b,
            b=b,
            t=t,
            r_out=r_out,
            fabrication=fabrication,
            classify_for=classify_for,
        )

    @staticmethod
    def create_angle_section(
        name: str,
        material: Material,
        h: float,
        b: float,
        t: float,
        r_root: float = 0.0,
        r_toe: float = 0.0,
        classify_for: Optional[str] = None,
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
        adv = Section._extract_advanced_props(analysis_section)

        _area = float(analysis_section.section_props.area)
        _ec3, _ = section_ec3(
            "angle",
            material.yield_stress,
            _area,
            fabrication="hot_rolled",
            h=h,
            b=b,
            t=t,
            r=r_root,
            classify_for=classify_for,
        )

        return Section(
            name=name,
            material=material,
            i_y=float(analysis_section.section_props.iyy_c),
            i_z=float(analysis_section.section_props.ixx_c),
            j=float(analysis_section.get_j()),
            area=_area,
            h=h,
            b=b,
            shape_path=shape_path,
            ec3=_ec3,
            **adv,
        )

    @staticmethod
    def create_welded_i_section(
        name: str,
        material: Material,
        h: float,
        b: float,
        t_f: float,
        t_w: float,
        classify_for: Optional[str] = None,
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
        adv = Section._extract_advanced_props(analysis_section)

        _area = float(analysis_section.section_props.area)
        _ec3, _ = section_ec3(
            "i",
            material.yield_stress,
            _area,
            fabrication="welded",
            h=h,
            b=b,
            t_f=t_f,
            t_w=t_w,
            classify_for=classify_for,
        )

        return Section(
            name=name,
            material=material,
            i_y=float(analysis_section.section_props.iyy_c),
            i_z=float(analysis_section.section_props.ixx_c),
            j=float(analysis_section.get_j()),
            area=_area,
            h=h,
            b=b,
            shape_path=shape_path,
            ec3=_ec3,
            **adv,
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
        classify_for: Optional[str] = None,
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
        adv = Section._extract_advanced_props(analysis_section)

        _area = float(analysis_section.section_props.area)
        _ec3, _ = section_ec3(
            "channel",
            material.yield_stress,
            _area,
            fabrication="cold_formed",
            h=h,
            b=b,
            t_f=t,
            t_w=t,
            r=r_out,
            classify_for=classify_for,
        )

        return Section(
            name=name,
            material=material,
            i_y=float(analysis_section.section_props.iyy_c),
            i_z=float(analysis_section.section_props.ixx_c),
            j=float(analysis_section.get_j()),
            area=_area,
            h=h,
            b=b,
            shape_path=shape_path,
            ec3=_ec3,
            **adv,
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
        classify_for: Optional[str] = None,
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
        adv = Section._extract_advanced_props(analysis_section)

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
            **adv,
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
