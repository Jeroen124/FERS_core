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
        Returns unit vectors (local_x, local_y, local_z) forming a right-handed local frame.
        local_x is along the member (start -> end).
        local_y and local_z are orthonormal and derived from a global reference direction.
        Applies rotation_angle as a roll about local_x (if non-zero).
        """
        dx = self.end_node.X - self.start_node.X
        dy = self.end_node.Y - self.start_node.Y
        dz = self.end_node.Z - self.start_node.Z
        length = float(np.sqrt(dx * dx + dy * dy + dz * dz))
        if length < 1e-12:
            raise ValueError("Start and end nodes are the same or too close to define a direction.")

        local_x = np.array([dx, dy, dz], dtype=float) / length

        # Use a pure global direction as reference (no addition of start node coordinates)
        reference_vector = np.array([0.0, 1.0, 0.0], dtype=float)
        cos_theta = float(np.dot(local_x, reference_vector))  # both are unit or unit-like
        if abs(cos_theta) > 1.0 - 1e-6:
            reference_vector = np.array([0.0, 0.0, 1.0], dtype=float)

        local_z = np.cross(local_x, reference_vector)
        norm_z = float(np.linalg.norm(local_z))
        if norm_z < 1e-12:
            # Last-resort fallback, though with the logic above this should be very rare
            reference_vector = np.array([1.0, 0.0, 0.0], dtype=float)
            local_z = np.cross(local_x, reference_vector)
            norm_z = float(np.linalg.norm(local_z))
            if norm_z < 1e-12:
                raise ValueError("Cannot define a valid local_z axis.")
        local_z /= norm_z

        local_y = np.cross(local_z, local_x)
        norm_y = float(np.linalg.norm(local_y))
        if norm_y < 1e-12:
            raise ValueError("Cannot define a valid local_y axis.")
        local_y /= norm_y

        # Apply roll about local_x by rotation_angle (radians)
        phi = float(self.rotation_angle or 0.0)
        if abs(phi) > 0.0:
            c = np.cos(phi)
            s = np.sin(phi)
            y_rot = c * local_y + s * local_z
            z_rot = -s * local_y + c * local_z
            local_y, local_z = y_rot, z_rot

        return local_x, local_y, local_z
