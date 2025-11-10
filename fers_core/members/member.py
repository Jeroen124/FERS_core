from typing import Optional, Union, List
import numpy as np

from fers_core.supports.nodalsupport import NodalSupport

from ..nodes.node import Node
from ..members.memberhinge import MemberHinge
from ..members.enums import MemberType, normalize_member_type
from ..members.section import Section


class Member:
    _member_counter = 1
    _all_members: List["Member"] = []

    def __init__(
        self,
        start_node: Node,
        end_node: Node,
        section: Optional[Section] = None,
        id: Optional[int] = None,
        start_hinge: Optional[MemberHinge] = None,
        end_hinge: Optional[MemberHinge] = None,
        classification: str = "",
        rotation_angle: float = 0.0,
        weight: Optional[float] = None,
        chi: Optional[float] = None,
        reference_member: Optional["Member"] = None,
        reference_node: Optional["Node"] = None,
        member_type: Union[MemberType, str] = MemberType.NORMAL,
    ):
        self.id = id or Member._member_counter
        if id is None:
            Member._member_counter += 1

        self.member_type: MemberType = normalize_member_type(member_type)

        # Enforce section rule: section may be None ONLY for Rigid
        if section is None and self.member_type is not MemberType.RIGID:
            raise ValueError(
                f"Section is required for member_type '{self.member_type.value}'. "
                f"It may be omitted only for 'Rigid' members."
            )

        self.start_node = start_node
        self.end_node = end_node
        self.section = section
        self.rotation_angle = float(rotation_angle)
        self.start_hinge = start_hinge
        self.end_hinge = end_hinge
        self.classification = classification
        self.chi = chi
        self.reference_member = reference_member
        self.reference_node = reference_node

        self.weight = float(weight) if weight is not None else self.weight()

        # Keep registry if you use it elsewhere
        Member._all_members.append(self)

    @classmethod
    def reset_counter(cls):
        cls._member_counter = 1

    @staticmethod
    def find_members_with_node(node: Node):
        return [m for m in Member._all_members if m.start_node == node or m.end_node == node]

    @staticmethod
    def get_all_members():
        return Member._all_members

    @classmethod
    def get_member_by_id(cls, id: int):
        """
        Find a member by its ID.
        """
        for member in cls._all_members:
            if member.id == id:
                return member
        return None

    def EA(self) -> float:
        """
        Axial rigidity. Requires a section. Rigid members have no EA in the solver;
        calling this for a member without section is an error.
        """
        if self.section is None:
            raise ValueError("Cannot compute EA: section is None.")
        E = self.section.material.e_mod
        A = self.section.area
        return E * A

    def Ei_y(self) -> float:
        if self.section is None:
            raise ValueError("Cannot compute E*Iy: section is None.")
        E = self.section.material.e_mod
        I = self.section.i_y
        return E * I

    def Ei_z(self) -> float:
        if self.section is None:
            raise ValueError("Cannot compute E*Iz: section is None.")
        E = self.section.material.e_mod
        I = self.section.i_z
        return E * I

    def length(self) -> float:
        dx = self.end_node.X - self.start_node.X
        dy = self.end_node.Y - self.start_node.Y
        dz = self.end_node.Z - self.start_node.Z
        return float((dx**2 + dy**2 + dz**2) ** 0.5)

    def length_x(self) -> float:
        return float(abs(self.end_node.X - self.start_node.X))

    def weight(self) -> float:
        """
        Returns member self-weight based on density * area * length when a section exists.
        For rigid members without a section, returns 0.0.
        """
        if self.section is None:
            return 0.0
        length = self.length()
        if length and self.section.material.density and self.section.area:
            return float(self.section.material.density * self.section.area * length)
        return 0.0

    def weight_per_mm(self) -> float:
        if self.section is None:
            return 0.0
        return float(self.section.material.density * self.section.area)

    def to_dict(self):
        return {
            "id": self.id,
            "start_node": self.start_node.to_dict(),
            "end_node": self.end_node.to_dict(),
            "section": self.section.id if self.section is not None else None,
            "rotation_angle": self.rotation_angle,
            "start_hinge": self.start_hinge.id if self.start_hinge else None,
            "end_hinge": self.end_hinge.id if self.end_hinge else None,
            "classification": self.classification,
            "weight": self.weight,
            "chi": self.chi,
            "reference_member": self.reference_member.id if self.reference_member else None,
            "reference_node": self.reference_node.id if self.reference_node else None,
            "member_type": self.member_type.value,
        }

    @classmethod
    def from_dict(
        cls,
        data: dict,
        *,
        nodes_by_id: dict[int, Node],
        nodal_supports_by_id: dict[int, "NodalSupport"] | None = None,
        sections_by_id: dict[int, Section] | None = None,
        hinges_by_id: dict[int, MemberHinge] | None = None,
        members_by_id: dict[int, "Member"] | None = None,
    ) -> "Member":
        """
        Construct a Member from its dict representation.

        Handles:
        - start_node / end_node as dict or id
        - section as dict or id
        - start_hinge / end_hinge by id
        - member_type as enum or string
        - reference_member / reference_node by id
        Registers itself into members_by_id if provided.
        """

        members_by_id = members_by_id if members_by_id is not None else {}
        sections_by_id = sections_by_id if sections_by_id is not None else {}
        hinges_by_id = hinges_by_id if hinges_by_id is not None else {}

        member_id = data.get("id")

        # --- start node ---
        start_node_data = data.get("start_node")
        if isinstance(start_node_data, dict):
            start_node = Node.get_or_create_from_dict(
                start_node_data,
                nodes_by_id=nodes_by_id,
                nodal_supports_by_id=nodal_supports_by_id,
            )
        else:
            start_node_id = data.get("start_node_id") or start_node_data
            start_node = nodes_by_id[start_node_id]

        # --- end node ---
        end_node_data = data.get("end_node")
        if isinstance(end_node_data, dict):
            end_node = Node.get_or_create_from_dict(
                end_node_data,
                nodes_by_id=nodes_by_id,
                nodal_supports_by_id=nodal_supports_by_id,
            )
        else:
            end_node_id = data.get("end_node_id") or end_node_data
            end_node = nodes_by_id[end_node_id]

        # --- section ---
        section = None
        section_data = data.get("section")
        if isinstance(section_data, dict):
            existing = sections_by_id.get(section_data.get("id"))
            if existing is None:
                section = Section.from_dict(section_data)
                sections_by_id[section.id] = section
            else:
                section = existing
        else:
            section_id = data.get("section_id") or section_data
            if section_id is not None:
                section = sections_by_id.get(section_id)

        # --- hinges ---
        start_hinge = None
        end_hinge = None

        start_hinge_id = data.get("start_hinge_id")
        if start_hinge_id is None and isinstance(data.get("start_hinge"), int):
            start_hinge_id = data["start_hinge"]
        if start_hinge_id is not None:
            start_hinge = hinges_by_id.get(start_hinge_id)

        end_hinge_id = data.get("end_hinge_id")
        if end_hinge_id is None and isinstance(data.get("end_hinge"), int):
            end_hinge_id = data["end_hinge"]
        if end_hinge_id is not None:
            end_hinge = hinges_by_id.get(end_hinge_id)

        # --- reference member ---
        reference_member = None
        ref_member_id = data.get("reference_member")
        if ref_member_id is not None and members_by_id is not None:
            reference_member = members_by_id.get(ref_member_id)

        # --- reference node ---
        reference_node = None
        ref_node = data.get("reference_node")
        if isinstance(ref_node, dict):
            reference_node = Node.get_or_create_from_dict(
                ref_node,
                nodes_by_id=nodes_by_id,
                nodal_supports_by_id=nodal_supports_by_id,
            )
        elif ref_node is not None:
            reference_node = nodes_by_id.get(ref_node)

        # --- build ---
        member = cls(
            start_node=start_node,
            end_node=end_node,
            section=section,
            id=member_id,
            start_hinge=start_hinge,
            end_hinge=end_hinge,
            classification=data.get("classification", "") or "",
            rotation_angle=float(data.get("rotation_angle", 0.0) or 0.0),
            weight=data.get("weight"),
            chi=data.get("chi"),
            reference_member=reference_member,
            reference_node=reference_node,
            member_type=data.get("member_type", MemberType.NORMAL),
        )

        if member_id is not None:
            members_by_id.setdefault(member_id, member)

        return member

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

        reference_vector = np.array([0.0, 1.0, 0.0], dtype=float)
        cos_theta = float(np.dot(local_x, reference_vector))
        if abs(cos_theta) > 1.0 - 1e-6:
            reference_vector = np.array([0.0, 0.0, 1.0], dtype=float)

        local_z = np.cross(local_x, reference_vector)
        norm_z = float(np.linalg.norm(local_z))
        if norm_z < 1e-12:
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

        phi = float(self.rotation_angle or 0.0)
        if abs(phi) > 0.0:
            c = np.cos(phi)
            s = np.sin(phi)
            y_rot = c * local_y + s * local_z
            z_rot = -s * local_y + c * local_z
            local_y, local_z = y_rot, z_rot

        return local_x, local_y, local_z
