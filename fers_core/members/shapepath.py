from typing import List, Optional
import matplotlib.pyplot as plt

from ..members.shapecommand import ShapeCommand


class ShapePath:
    _shape_counter = 1

    def __init__(self, name: str, shape_commands: List[ShapeCommand], id: Optional[int] = None):
        """
        Initializes a ShapePath object.
        Parameters:
        name (str): Name of the shape (e.g., "IPE100", "RHS 100x50x4").
        shape_commands (List[ShapeCommand]): List of shape commands defining the section geometry.
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

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "shape_commands": [cmd.to_dict() for cmd in self.shape_commands],
        }

    @staticmethod
    def create_ipe_profile(h: float, b: float, t_f: float, t_w: float, r: float) -> List[ShapeCommand]:
        """
        Generates shape commands for an IPE profile.
        Parameters:
        h (float): Total height of the IPE profile.
        b (float): Flange width.
        t_f (float): Flange thickness.
        t_w (float): Web thickness.
        r (float): Fillet radius (currently unused).
        Returns:
        List[ShapeCommand]: List of shape commands defining the IPE geometry.
        """
        commands = [
            ShapeCommand("moveTo", z=-b / 2, y=h / 2),  # 0
            ShapeCommand("lineTo", z=b / 2, y=h / 2),  # 1
            ShapeCommand("lineTo", z=b / 2, y=h / 2 - t_f),  # 2
            ShapeCommand("lineTo", z=t_w / 2, y=h / 2 - t_f),  # 3
            ShapeCommand("lineTo", z=t_w / 2, y=-h / 2 + t_f),  # 4
            ShapeCommand("lineTo", z=b / 2, y=-h / 2 + t_f),  # 5
            ShapeCommand("lineTo", z=b / 2, y=-h / 2),  # 6
            ShapeCommand("lineTo", z=-b / 2, y=-h / 2),  # 7
            ShapeCommand("lineTo", z=-b / 2, y=-h / 2 + t_f),  # 8
            ShapeCommand("lineTo", z=-t_w / 2, y=-h / 2 + t_f),  # 9
            ShapeCommand("lineTo", z=-t_w / 2, y=h / 2 - t_f),  # 10
            ShapeCommand("lineTo", z=-b / 2, y=h / 2 - t_f),  # 11
            ShapeCommand("closePath"),
        ]
        return commands

    def plot(self, show_nodes: bool = True):
        """
        Plots the shape on the yz plane, with y as the horizontal axis and z as the vertical axis.
        Parameters:
        show_nodes (bool): Whether to display node numbers and positions. Default is True.
        """
        y, z = [], []
        node_coords = []  # To store node coordinates for plotting
        start_y, start_z = None, None  # To track the starting point for closePath
        node_count = 0

        for command in self.shape_commands:
            if command.command == "moveTo":
                if z and y:  # If not empty, draw the previous path
                    plt.plot(z, y, "b-")
                    z, y = [], []
                z.append(command.z)
                y.append(command.y)
                node_coords.append((command.z, command.y, node_count))
                start_z, start_y = command.z, command.y
                node_count += 1
            elif command.command == "lineTo":
                z.append(command.z)
                y.append(command.y)
                node_coords.append((command.z, command.y, node_count))
                node_count += 1
            elif command.command == "closePath":
                if start_z is not None and start_y is not None:
                    z.append(start_z)
                    y.append(start_y)
                plt.plot(z, y, "b-")
                z, y = [], []

        # Plot node numbers if enabled
        if show_nodes:
            for ny, nz, nnum in node_coords:
                plt.scatter(ny, nz, color="red")  # Plot the node as a red point
                plt.text(ny, nz, str(nnum), color="red", fontsize=10, ha="right")

        plt.axvline(0, color="black", linestyle="--")  # y-axis (z=0)
        plt.axhline(0, color="black", linestyle="--")  # z-axis (y=0)

        plt.axis("equal")
        plt.title(self.name)
        plt.xlabel("Z (Vertical)")
        plt.ylabel("Y (Horizontal)")
        plt.grid(True)
        plt.show()

    def get_shape_geometry(self):
        """
        Converts the shape commands into nodes and edges for plotting or extrusion.

        Returns:
        - coords (list of tuple): A list of (y, z) coordinates defining the vertices of the shape.
        - edges (list of tuple): A list of (start_index, end_index) representing connections between nodes.
        """
        coords = []  # To store all the (y, z) coordinates
        edges = []  # To store edges as (start_index, end_index)
        start_index = None  # To track the starting index for 'closePath'
        node_index = 0  # Index counter for vertices

        for command in self.shape_commands:
            if command.command == "moveTo":
                # Record the starting point for closePath
                start_index = node_index
                coords.append((command.y, command.z))
                node_index += 1

            elif command.command == "lineTo":
                # Add a vertex and connect it to the previous node
                coords.append((command.y, command.z))
                edges.append((node_index - 1, node_index))
                node_index += 1

            elif command.command == "closePath":
                if start_index is not None:
                    # Close the loop by connecting the last node to the start node
                    edges.append((node_index - 1, start_index))

        return coords, edges
