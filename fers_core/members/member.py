from fers_core.nodes.node import Node

from typing import Optional  

from fers_core.members.memberhinge import MemberHinge
from fers_core.members.enums import MemberType
from fers_core.members.section import Section

class Member:
    _member_counter = 1
    _all_members = []

    def __init__(
        self,
        start_node: Node,
        end_node: Node,
        section: Section,
        start_hinge: MemberHinge = None,
        end_hinge: MemberHinge = None,
        pk: int = None,
        classification: str = "",
        rotation_angle: float = 0.0,
        weight: float = None,
        chi: float = None,
        reference_member: Optional['Member'] = None,  
        reference_node: Optional['Node'] = None,
        member_type: str = MemberType.NORMAL 
    ):
        # Handle member numbering with an optional classification
        if pk is None:
            self.pk = Member._member_counter
            Member._member_counter += 1
        else:
            self.pk = pk

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

    def to_dict(self):
        if self.rotation_angle is not None:
            rotation = self.rotation_angle
        else:
            rotation = 0.0
        return {
            str(self.pk): {
                "type": "normal",
                "node_A": self.start_node.pk,
                "node_B": self.end_node.pk,
                "section_id": self.section.id,
                "rotation_angle": rotation,
            }
        }

    @classmethod
    def reset_counter(cls):
        cls._member_counter = 1

    def get_member_by_pk(cls, member_pk: int):
        """
        Class method to find a member by its ID.

        Args:
            member_id (str): The ID of the member to find.

        Returns:
            Member: The found member object or None if not found.
        """
        for member in cls._all_members:
            if member.pk == member_pk:
                return member
        return None

    def EA(self):
        E = self.section.material.E_mod
        A = self.section.A
        return E * A

    def EI(self):
        E = self.section.material.E_mod
        I = self.section.I_y  # noqa: E741
        return E * I

    def EI_weak_axis(self):
        E = self.section.material.E_mod
        I = self.section.I_z  # noqa: E741
        return E * I

    def length(self):
        dx = self.end_node.X - self.start_node.X
        dy = self.end_node.Y - self.start_node.Y
        dz = self.end_node.Z - self.start_node.Z
        return (dx**2 + dy**2 + dz**2) ** 0.5

    def length_x(self):
        dx = abs(self.end_node.X - self.start_node.X)
        return dx

    def weight(self):
        length = self.length()
        return self.section.material.density * self.section.A * length

    def weight_per_mm(self):
        return self.section.material.density * self.section.A 

    def split_member_into_three(member):
        total_length = member.length()
        
        # Calculate the coordinates for the new nodes
        start_node = member.start_node
        end_node = member.end_node

        def interpolate_node(node1, node2, fraction):
            x = node1.X + fraction * (node2.X - node1.X)
            y = node1.Y + fraction * (node2.Y - node1.Y)
            z = node1.Z + fraction * (node2.Z - node1.Z)
            return Node(X=x, Y=y, Z=z)
        
        # Create new nodes for the split points
        node_2_percent_start = interpolate_node(start_node, end_node, 0.02)
        node_98_percent_end = interpolate_node(start_node, end_node, 0.98)

        # Create new members with the appropriate sections
        first_member = Member(start_node, node_2_percent_start, member.section, member.start_hinge, None)
        middle_member = Member(node_2_percent_start, node_98_percent_end, member.section, None, None, classification=member.classification)
        last_member = Member(node_98_percent_end, end_node, member.section, None, member.end_hinge)
        
        return first_member, middle_member, last_member


    @staticmethod
    def find_members_with_node(node):
        return [member for member in Member._all_members if member.start_node == node or member.end_node == node]

    @staticmethod
    def get_all_members():
        # Static method to retrieve all Member objects
        return Member._all_members
