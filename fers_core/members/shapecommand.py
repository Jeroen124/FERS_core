from typing import Optional


class ShapeCommand:
    def __init__(
        self,
        command: str,
        y: Optional[float] = None,
        z: Optional[float] = None,
        r: Optional[float] = None,
        control_y1: Optional[float] = None,
        control_z1: Optional[float] = None,
        control_y2: Optional[float] = None,
        control_z2: Optional[float] = None,
    ):
        """
        Represents a single shape command.
        Parameters:
        command (str): The type of command (e.g., "moveTo", "lineTo", "closePath").
        y (float, optional): Y-coordinate.
        z (float, optional): Z-coordinate.
        r (float, optional): Radius (used for arcs).
        control_y1 (float, optional): First control point Y-coordinate (for bezier curves).
        control_z1 (float, optional): First control point Z-coordinate (for bezier curves).
        control_y2 (float, optional): Second control point Y-coordinate (for bezier curves).
        control_z2 (float, optional): Second control point Z-coordinate (for bezier curves).
        """
        self.command = command
        self.y = y
        self.z = z
        self.r = r
        self.control_y1 = control_y1
        self.control_z1 = control_z1
        self.control_y2 = control_y2
        self.control_z2 = control_z2

    def to_dict(self) -> dict:
        """
        Converts the ShapeCommand to a dictionary.
        Returns:
        dict: The dictionary representation of the command.
        """
        return {
            "command": self.command,
            "y": self.y,
            "z": self.z,
            "r": self.r,
            "control_y1": self.control_y1,
            "control_z1": self.control_z1,
            "control_y2": self.control_y2,
            "control_z2": self.control_z2,
        }
