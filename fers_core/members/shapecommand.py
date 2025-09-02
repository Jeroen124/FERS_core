from typing import Optional


class ShapeCommand:
    def __init__(
        self,
        command: str,
        y: Optional[float] = None,
        z: Optional[float] = None,
        r: Optional[float] = None,
        center_y: Optional[float] = None,
        center_z: Optional[float] = None,
        theta0: Optional[float] = None,
        theta1: Optional[float] = None,
    ):
        """
        Represents a single shape command.

        Supported commands:
            - "moveTo":     uses (y, z)
            - "lineTo":     uses (y, z)
            - "arcTo":      uses (center_y, center_z, r, theta0, theta1) and ignores (y, z)
            - "closePath":  no coordinates required
        """
        self.command = command
        self.y = y
        self.z = z
        self.r = r

        # Arc parameters (true input, not Bézier)
        self.center_y = center_y
        self.center_z = center_z
        self.theta0 = theta0
        self.theta1 = theta1

    def to_dict(self) -> dict:
        """
        Converts the ShapeCommand to a dictionary.
        """
        return {
            "command": self.command,
            "y": self.y,
            "z": self.z,
            "r": self.r,
            "center_y": self.center_y,
            "center_z": self.center_z,
            "theta0": self.theta0,
            "theta1": self.theta1,
        }
