import matplotlib.pyplot as plt
import numpy as np

from FERS_core.members.member import Member
from typing import Optional


class MemberSet:
    _member_set_counter = 1

    def __init__(
        self,
        members: Optional[list[Member]] = None,
        classification: Optional[str] = None,
        l_y: Optional[float] = None,
        l_z: Optional[float] = None,
        id: Optional[int] = None,
    ):
        self.memberset_id = id or MemberSet._member_set_counter
        if id is None:
            MemberSet._member_set_counter += 1

        self.members_id = [member.id for member in members] if members else []
        self.members = members if members is not None else []
        self.l_y = l_y
        self.l_z = l_z
        self.classification = classification

    @classmethod
    def reset_counter(cls):
        cls._member_set_counter = 1

    def to_dict(self):
        # Get unique materials and sections using get_unique methods
        return {
            "id": self.memberset_id,
            "l_y": self.l_y,
            "l_z": self.l_z,
            "classification": self.classification,
            "members": [member.to_dict() for member in self.members],
        }

    @staticmethod
    def find_member_sets_containing_member(id, all_member_sets):
        return [member_set for member_set in all_member_sets if id in member_set.members_id]

    @staticmethod
    def aggregate_properties(member_set, all_members):
        # Assuming all_members is a dictionary with member numbers as keys
        total_length = 0
        for id in member_set.members_id:
            member = all_members[id]
            total_length += Member.calculate_length(member)
        return {"total_length": total_length}

    def add_member(self, member: Member):
        """Add a single member to the MemberSet."""
        self.members.append(member)
        self.members_id.append(member.id)

    def plot(self, plane="yz", fig=None, ax=None, set_aspect=True, show_title=True, show_legend=True):
        """
        Plot the members in the MemberSet on the specified plane ('xy' or 'xz' or 'yz'),
        including nodes plotted as dots.

        Parameters:
        - plane: A string specifying the plot plane, either 'xy' or 'xz'.
        """
        if fig is None or ax is None:
            fig, ax = plt.subplots()
        # Loop through members and plot them
        for member in self.members:
            start_node = member.start_node
            end_node = member.end_node

            if plane == "xy":
                primary_values = [start_node.X, end_node.X]
                secondary_values = [start_node.Y, end_node.Y]
                ax.set_xlabel("X Coordinate")
                ax.set_ylabel("Y Coordinate")
                ax.plot(start_node.X, start_node.Y, "o", color="red")  # Start node
                ax.plot(end_node.X, end_node.Y, "o", color="red")  # End node

            elif plane == "xz":
                primary_values = [start_node.X, end_node.X]
                secondary_values = [start_node.Z, end_node.Z]
                ax.set_xlabel("X Coordinate")
                ax.set_ylabel("Z Coordinate")
                ax.plot(start_node.X, start_node.Z, "o", color="red")  # Start node
                ax.plot(end_node.X, end_node.Z, "o", color="red")  # End node

            elif plane == "yz":
                primary_values = [start_node.Z, end_node.Z]
                secondary_values = [start_node.Y, end_node.Y]
                ax.set_xlabel("Z Coordinate")
                ax.set_ylabel("Y Coordinate")

                ax.plot(start_node.Z, start_node.Y, "o", color="red")  # Start node
                ax.plot(end_node.Z, end_node.Y, "o", color="red")  # End node

            else:
                raise ValueError("Invalid plane specified. Use 'xy', 'xz' or 'yz'.")

            # Plot member line
            ax.plot(primary_values, secondary_values, label=f"Member {member.id}")
            # Plot start and end nodes as dots

        # Customize plot settings
        if set_aspect:
            ax.set_aspect("equal", adjustable="box")
        if show_title:
            ax.set_title(f"Member Set: {self.id}")
        # Set the legend outside the plot
        if not show_legend:
            ax.legend_ = None
        else:
            ax.legend(loc="upper left", bbox_to_anchor=(1, 1))

        plt.tight_layout()

    def plot_nodes(self, plane="yz"):
        """
        Plot the members in the MemberSet on the specified plane ('xy', 'xz', or 'yz'),
        including nodes plotted as dots and displaying node numbers as floating text.
        """
        fig, ax = plt.subplots()

        # Loop through members and plot them, including node numbers
        for member in self.members:
            start_node = member.start_node
            end_node = member.end_node

            # Determine plotting coordinates based on the specified plane
            if plane == "xy":
                start_coords = (start_node.X, start_node.Y)
                end_coords = (end_node.X, end_node.Y)
                label_axis = ("X Coordinate", "Y Coordinate")
            elif plane == "xz":
                start_coords = (start_node.X, start_node.Z)
                end_coords = (end_node.X, end_node.Z)
                label_axis = ("X Coordinate", "Z Coordinate")
            elif plane == "yz":
                start_coords = (start_node.Y, start_node.Z)
                end_coords = (end_node.Y, end_node.Z)
                label_axis = ("Y Coordinate", "Z Coordinate")
            else:
                raise ValueError("Invalid plane specified. Use 'xy', 'xz' or 'yz'.")

            # Plot start and end nodes as dots
            ax.plot(*start_coords, "o", color="red")
            ax.plot(*end_coords, "o", color="red")

            # Plot member line
            ax.plot(
                [start_coords[0], end_coords[0]],
                [start_coords[1], end_coords[1]],
                label=f"Member {member.id}",
            )

            # Display node numbers as floating text near each node
            ax.text(start_coords[0], start_coords[1], f"{start_node.id}", verticalalignment="bottom")
            ax.text(end_coords[0], end_coords[1], f"{end_node.id}", verticalalignment="bottom")

        # Set labels and title
        ax.set_xlabel(label_axis[0])
        ax.set_ylabel(label_axis[1])
        ax.set_title(f"Member Set: {self.id}")

        # Set the legend outside the plot
        ax.legend(loc="upper left", bbox_to_anchor=(1, 1))

        plt.tight_layout()  # Adjust the layout to make room for the legend

        # Show the plot
        plt.show()

    def get_unique_sections(self, ids_only=False):
        """
        Returns a list of unique sections used in the MemberSet, based on section id.

        Parameters:
            ids_only (bool): If True, returns only the unique section IDs. If False, returns section objects.
                           Defaults to False.

        Returns:
            list: List of unique section objects or section IDs.
        """
        unique_sections = {}
        for member in self.members:
            section = member.section
            unique_sections[section.id] = section

        if ids_only:
            return list(unique_sections.keys())
        return list(unique_sections.values())

    def get_unique_materials(self, ids_only=False):
        """
        Returns a list of unique materials used in the MemberSet, based on material id.

        Parameters:
            ids_only (bool): If True, returns only the unique material IDs. If False, returns material objects
                           Defaults to False.

        Returns:
            list: List of unique material objects or material IDs.
        """
        unique_materials = {}
        for member in self.members:
            material = member.section.material
            unique_materials[material.id] = material

        if ids_only:
            return list(unique_materials.keys())
        return list(unique_materials.values())

    def get_unique_memberhinges(self, ids_only=False):
        """
        Returns a list of unique hinges used in the MemberSet, based on hinge id.

        Parameters:
            ids_only (bool): If True, returns only the unique hinge IDs. If False, returns the hinge objects.
                           Defaults to False.

        Returns:
            list: List of unique hinge objects or hinge IDs.
        """
        unique_hinges = {}
        for member in self.members:
            if member.start_hinge:
                unique_hinges[member.start_hinge.id] = member.start_hinge
            if member.end_hinge:
                unique_hinges[member.end_hinge.id] = member.end_hinge

        if ids_only:
            return list(unique_hinges.keys())
        return list(unique_hinges.values())

    def get_longest_member(self):
        """
        Returns the longest member in the MemberSet.

        Returns:
            Member: The member with the longest length. Returns None if the MemberSet is empty.
        """
        if not self.members:
            return None

        longest_member = max(self.members, key=lambda member: member.length())
        return longest_member

    def get_minimal_Wy_el(self):
        """
        Returns the member with the smallest moment of inertia about the local y-axis (W_y).
        """
        if not self.members:
            return None
        unique_sections = self.get_unique_sections()

        smallest_Wy_section = min(unique_sections, key=lambda section: section.W_y_el)
        return smallest_Wy_section.W_y_el

    def get_minimal_Wz_el(self):
        """
        Returns the member with the smallest moment of inertia about the local z-axis (W_z).
        """
        if not self.members:
            return None
        unique_sections = self.get_unique_sections()

        smallest_Wz_section = min(unique_sections, key=lambda section: section.W_z_el)
        return smallest_Wz_section.W_z_el

    def get_minimal_Iy(self):
        """
        Returns the member with the smallest moment of inertia about the local y-axis (i_y).
        """
        if not self.members:
            return None
        unique_sections = self.get_unique_sections()

        smallest_Iy_section = min(unique_sections, key=lambda section: section.i_y)
        return smallest_Iy_section.i_y

    def get_minimal_Iz(self):
        """
        Returns the member with the smallest moment of inertia about the local z-axis (i_z).
        """
        if not self.members:
            return None
        unique_sections = self.get_unique_sections()

        smallest_Iz_section = min(unique_sections, key=lambda section: section.i_z)
        return smallest_Iz_section.i_z

    def get_minimal_yield_stress(self):
        """
        Returns the material with the lowest yield stress among the members.
        """
        if not self.members:
            return None
        # Extract all unique materials first to avoid comparing the same material multiple times
        unique_materials = self.get_unique_materials()
        lowest_yield_stress_material = min(unique_materials, key=lambda material: material.yield_stress)
        return lowest_yield_stress_material.yield_stress

    def get_first_member(self):
        """
        Returns the start node of the first member in the MemberSet.

        Returns:
            Node: The start node of the first member.
        """
        if self.members:
            return self.members[0]
        else:
            return None

    def get_last_member(self):
        """
        Returns the last member in the MemberSet.

        Returns:
            member: The last member in the MemberSet.
        """
        if self.members:
            return self.members[-1]
        else:
            return None

    def get_start_node_of_first_member(self):
        """
        Returns the start node of the first member in the MemberSet.

        Returns:
            Node: The start node of the first member.
        """
        if self.members:
            return self.members[0].start_node
        else:
            return None

    def get_end_node_of_last_member(self):
        """
        Returns the end node of the last member in the MemberSet.

        Returns:
            Node: The end node of the last member.
        """
        if self.members:
            return self.members[-1].end_node
        else:
            return None

    def find_members_by_first_node(self, node):
        """
        Finds all members whose start node matches the given node.

        Args:
            node (Node): The node to search for at the start of members.

        Returns:
            List[Member]: A list of members starting with the given node.
        """
        matching_members = []
        for member in self.members:
            if member.start_node == node:
                matching_members.append(member)
        return matching_members

    def length(self):
        start_node = self.get_start_node_of_first_member()
        end_node = self.get_end_node_of_last_member()

        dx = end_node.X - start_node.X
        dy = end_node.Y - start_node.Y
        dz = end_node.Z - start_node.Z
        return (dx**2 + dy**2 + dz**2) ** 0.5

    def get_all_nodes(self):
        """
        Returns a list of all unique nodes that are part of the MemberSet.

        Returns:
            list[Node]: A list of unique Node instances in the MemberSet.
        """
        unique_nodes = {}
        for member in self.members:
            unique_nodes[member.start_node.id] = member.start_node
            unique_nodes[member.end_node.id] = member.end_node

        return list(unique_nodes.values())

    def find_node_with_classification(self, classification):
        """
        Find the first node with the given classification.

        Args:
            classification (str): The classification to search for.

        Returns:
            Node: The first node with the specified classification, or None if no such node is found.
        """
        for node in self.get_all_nodes():
            if node.classification == classification:
                return node
        return None

    def get_highest_node(self):
        """
        Finds and returns the node with the highest y-coordinate.

        Returns:
            Node: Returns node with the highest y-coordinate.
        """
        highest_node = None

        for node in self.get_all_nodes():
            if highest_node is None or node.Y > highest_node.Y:
                highest_node = node

        return highest_node

    def rotate_nodes(self, axis, point, angle):
        """
        Rotate all nodes in the MemberSet around a specified axis and point.

        Args:
            axis (tuple): The axis of rotation as a 3-tuple (x, y, z).
            point (tuple): The point around which to rotate as a 3-tuple (x, y, z).
            angle (float): The rotation angle in degrees.
        """
        axis_sum = sum(axis)
        direction_multiplier = -1 if axis_sum < 0 else 1
        angle_rad = np.radians(angle) * direction_multiplier

        for node in self.get_all_nodes():
            rel_x, rel_y, rel_z = node.X - point[0], node.Y - point[1], node.Z - point[2]
            if abs(axis[0]) == 1:  # Rotation about the X-axis
                new_y = rel_y * np.cos(angle_rad) - rel_z * np.sin(angle_rad)
                new_z = rel_y * np.sin(angle_rad) + rel_z * np.cos(angle_rad)
                node.Y, node.Z = new_y + point[1], new_z + point[2]
            elif abs(axis[1]) == 1:  # Rotation about the Y-axis
                new_x = rel_z * np.sin(angle_rad) + rel_x * np.cos(angle_rad)
                new_z = rel_z * np.cos(angle_rad) - rel_x * np.sin(angle_rad)
                node.X, node.Z = new_x + point[0], new_z + point[2]
            elif abs(axis[2]) == 1:  # Rotation about the Z-axis
                new_x = rel_x * np.cos(angle_rad) - rel_y * np.sin(angle_rad)
                new_y = rel_x * np.sin(angle_rad) + rel_y * np.cos(angle_rad)
                node.X, node.Y = new_x + point[0], new_y + point[1]
            else:
                raise ValueError("Invalid axis specified. Axis must be along X, Y, or Z.")
