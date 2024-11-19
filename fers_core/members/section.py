from typing import Optional
from FERS_core.members.material import Material
from FERS_core.members.shapepath import ShapePath


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
        i_y (float): Moment of inertia about the y-axis, indicating resistance to bending.
        i_z (float): Moment of inertia about the z-axis, indicating resistance to torsion.
        j (float): Torsional constant, indicating resistance to torsion.
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
