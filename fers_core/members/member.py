from ..nodes.node import Node

from typing import Optional
import numpy as np

from ..members.memberhinge import MemberHinge
from ..members.enums import MemberType
from ..members.section import Section


class Member:
    _member_counter = 1
    _all_members = []

    def __init__(
        self,
        start_node: Node,
        end_node: Node,
        section: Section,
        id: Optional[int] = None,
        start_hinge: Optional[MemberHinge] = None,
        end_hinge: Optional[MemberHinge] = None,
        classification: str = "",
        rotation_angle: float = 0.0,
        weight: Optional[float] = None,
        chi: Optional[float] = None,
        reference_member: Optional["Member"] = None,
        reference_node: Optional["Node"] = None,
        member_type: MemberType = MemberType.NORMAL,
    ):
        self.id = id or Member._member_counter
        if id is None:
            Member._member_counter += 1
        self.rotation_angle = rotation_angle
        self.start_node = start_node
        self.end_node = end_node
        self.section = section
        self.rotation_angle = rotation_angle
        self.start_hinge = start_hinge
        self.end_hinge = end_hinge
        self.classification = classification
        self.weight = weight if weight is not None else self.weight()
        self.chi = chi
        self.reference_member = reference_member
        self.reference_node = reference_node
        self.member_type = member_type

    @classmethod
    def reset_counter(cls):
        cls._member_counter = 1

    @staticmethod
    def find_members_with_node(node):
        return [
            member for member in Member._all_members if member.start_node == node or member.end_node == node
        ]

    @staticmethod
    def get_all_members():
        # Static method to retrieve all Member objects
        return Member._all_members

    def get_member_by_id(cls, id: int):
        """
        Class method to find a member by its ID.

        Args:
            id (str): The ID of the member to find.

        Returns:
            Member: The found member object or None if not found.
        """
        for member in cls._all_members:
            if member.id == id:
                return member
        return None

    def EA(self):
        E = self.section.material.e_mod
        A = self.section.area
        return E * A

    def Ei_y(self):
        E = self.section.material.e_mod
        I = self.section.i_y  # noqa: E741
        return E * I

    def Ei_z(self):
        E = self.section.material.e_mod
        I = self.section.i_z  # noqa: E741
        return E * I

    def length(self):
        dx = self.end_node.X - self.start_node.X
        dy = self.end_node.Y - self.start_node.Y
        dz = self.end_node.Z - self.start_node.Z
        return (dx**2 + dy**2 + dz**2) ** 0.5

    def length_x(self):
        dx = abs(self.end_node.X - self.start_node.X)
        return dx

    def weight(self) -> float:
        length = self.length()
        if length and self.section.material.density and self.section.area:
            return self.section.material.density * self.section.area * length
        return 0.0

    def weight_per_mm(self):
        return self.section.material.density * self.section.area

    def to_dict(self):
        return {
            "id": self.id,
            "start_node": self.start_node.to_dict(),
            "end_node": self.end_node.to_dict(),
            "section": self.section.id,
            "rotation_angle": self.rotation_angle,
            "start_hinge": self.start_hinge.id if self.start_hinge else None,
            "end_hinge": self.end_hinge.id if self.end_hinge else None,
            "classification": self.classification,
            "weight": self.weight,
            "chi": self.chi,
            "reference_member": self.reference_member.id if self.reference_member else None,
            "reference_node": self.reference_node.id if self.reference_node else None,
            "member_type": str(self.member_type.value)
            if isinstance(self.member_type, MemberType)
            else self.member_type,
        }

    def local_coordinate_system(self):
        """
        Calculates the local coordinate system (x, y, z) for the member.

        Returns:
        - local_x (numpy array): The local x-axis (unit vector along the member's axis).
        - local_y (numpy array): The local y-axis (unit vector perpendicular to x and z).
        - local_z (numpy array): The local z-axis (unit vector orthogonal to x and y).
        """
        # Compute the local x-axis (direction vector from start_node to end_node)
        dx = self.end_node.X - self.start_node.X
        dy = self.end_node.Y - self.start_node.Y
        dz = self.end_node.Z - self.start_node.Z
        length = np.sqrt(dx**2 + dy**2 + dz**2)
        start_node_array = np.array([self.start_node.X, self.start_node.Y, self.start_node.Z])
        if length < 1e-12:
            raise ValueError("Start and end nodes are the same or too close to define a direction.")

        local_x = np.array([dx / length, dy / length, dz / length])

        # Define the primary reference vector (global Y-axis)
        primary_ref = np.array([0, 1, 0]) + start_node_array

        # Check if local_x is parallel or nearly parallel to the primary reference vector
        cos_theta = np.dot(local_x, primary_ref) / (np.linalg.norm(local_x) * np.linalg.norm(primary_ref))
        if np.abs(cos_theta) > 1.0 - 1e-6:
            # If parallel, choose an alternative reference vector (global Z-axis)
            reference_vector = np.array([0, 0, 1]) + start_node_array
        else:
            # Otherwise, use the primary reference vector
            reference_vector = primary_ref

        # Compute the local z-axis as the cross product of local_x and reference_vector
        local_z = np.cross(local_x, reference_vector)
        norm_z = np.linalg.norm(local_z)
        if norm_z < 1e-12:
            # If the cross product is near zero, choose a different reference vector
            # Here, we can choose the global X-axis or another non-parallel vector
            reference_vector = np.array([1, 0, 0]) + start_node_array
            local_z = np.cross(local_x, reference_vector)
            norm_z = np.linalg.norm(local_z)
            if norm_z < 1e-12:
                raise ValueError(
                    "Cannot define a valid local_z axis; local_x is collinear with all reference vectors."
                )

        local_z /= norm_z

        # Compute the local y-axis as the cross product of local_z and local_x
        local_y = np.cross(local_z, local_x)
        norm_y = np.linalg.norm(local_y)
        if norm_y < 1e-12:
            raise ValueError("Cannot define local_y axis; local_z and local_x are collinear.")

        local_y /= norm_y

        return local_x, local_y, local_z
