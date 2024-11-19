from typing import List, Dict, Optional


class ShapePath:
    _shape_counter = 1

    def __init__(self, name: str, shape_commands: List[Dict], id: Optional[int] = None):
        """
        Initializes a ShapePath object.
        Parameters:
        name (str): Name of the shape (e.g., "IPE100", "RHS 100x50x4").
        shape_commands (List[Dict]): List of shape commands defining the section geometry.
        id (int, optional): Unique identifier for the shape path.
        """
        self.id = id or ShapePath._shape_counter
        if id is None:
            ShapePath._shape_counter += 1
        self.name = name
        self.shape_commands = shape_commands

    @classmethod
    def reset_counter(cls):
        cls._shape_counter = 1

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "shapeCommands": self.shape_commands,
        }

    @staticmethod
    def create_ipe_profile(h: float, b: float, t_f: float, t_w: float, r: float) -> List[Dict]:
        """
        Generates shape commands for an IPE profile.
        Parameters:
        h (float): Total height of the IPE profile.
        b (float): Flange width.
        t_f (float): Flange thickness.
        t_w (float): Web thickness.
        r (float): Fillet radius (currently unused).
        Returns:
        List[Dict]: List of shape commands defining the IPE geometry.
        """
        commands = []

        # Top flange (starting at top-left corner)
        commands.append({"command": "moveTo", "x": -b / 2, "y": h / 2})
        commands.append({"command": "lineTo", "x": b / 2, "y": h / 2})
        commands.append({"command": "lineTo", "x": b / 2, "y": h / 2 - t_f})
        commands.append({"command": "lineTo", "x": t_w / 2, "y": h / 2 - t_f})

        # Web
        commands.append({"command": "lineTo", "x": t_w / 2, "y": -h / 2 + t_f})
        commands.append({"command": "lineTo", "x": -t_w / 2, "y": -h / 2 + t_f})

        # Bottom flange
        commands.append({"command": "lineTo", "x": -t_w / 2, "y": -h / 2 + t_f})
        commands.append({"command": "lineTo", "x": -b / 2, "y": -h / 2})
        commands.append({"command": "lineTo", "x": b / 2, "y": -h / 2})
        commands.append({"command": "lineTo", "x": b / 2, "y": -h / 2 + t_f})
        commands.append({"command": "lineTo", "x": -b / 2, "y": -h / 2 + t_f})

        # Close the path
        commands.append({"command": "closePath"})

        return commands
