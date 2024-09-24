class Section:
    def __init__(self, id: int, name: str, material: str, h: float, b: float, I_y: float, I_z: float, area: float, t_w: float = None, t_f: float = None):
        """
        Initializes a Section object.

        Parameters:
        id (int): Unique identifier for the section.
        name (str): Name of the section.
        material (str): Material type of the section (e.g., steel, concrete).
        h (float): Height of the section.
        b (float): Width of the section.
        I_y (float): Moment of inertia about the y-axis.
        I_z (float): Moment of inertia about the z-axis.
        area (float): Area of the section.
        t_w (float, optional): Thickness of the web (default is None).
        t_f (float, optional): Thickness of the flange (default is None).
        """
        self.id = id
        self.name = name
        self.material = material
        self.h = h
        self.b = b
        self.I_y = I_y
        self.I_z = I_z
        self.area = area
        self.t_w = t_w
        self.t_f = t_f
