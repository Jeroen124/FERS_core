from typing import Optional


class LoadCase:
    _load_case_counter = 1
    _all_load_cases = []

    def __init__(
        self,
        name: Optional[str] = None,
        id: Optional[int] = None,
        nodal_loads: Optional[list] = None,
        nodal_moments: Optional[list] = None,
        distributed_loads: Optional[list] = None,
        rotation_imperfections: Optional[list] = None,
        translation_imperfections: Optional[list] = None,
    ):
        self.id = id or LoadCase._load_case_counter
        if id is None:
            LoadCase._load_case_counter += 1
        if name is None:
            self.name = f"Loadcase {self.id}"
        else:
            self.name = name

        self.nodal_loads = nodal_loads if nodal_loads is not None else []
        self.nodal_moments = nodal_moments if nodal_moments is not None else []
        self.distributed_loads = distributed_loads if distributed_loads is not None else []
        self.rotation_imperfections = rotation_imperfections if rotation_imperfections is not None else []
        self.translation_imperfections = (
            translation_imperfections if translation_imperfections is not None else []
        )

        LoadCase._all_load_cases.append(self)

    def add_nodal_load(self, nodal_load):
        self.nodal_loads.append(nodal_load)

    def add_nodal_moment(self, nodal_load):
        self.nodal_moments.append(nodal_load)

    def add_distributed_load(self, distributed_loads):
        self.distributed_loads.append(distributed_loads)

    def add_rotation_imperfection(self, rotation_imperfection):
        self.imperfection_loads.append(rotation_imperfection)

    def add_translation_imperfection(self, translation_imperfection):
        self.imperfection_loads.append(translation_imperfection)

    @classmethod
    def reset_counter(cls):
        cls._load_case_counter = 1

    @classmethod
    def names(cls):
        return cls._all_load_cases.name

    @classmethod
    def get_all_load_cases(cls):
        return cls._all_load_cases

    @classmethod
    def get_by_name(cls, name: str):
        for load_case in cls._all_load_cases:
            if load_case.name == name:
                return load_case
        return None

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "nodal_loads": [nl.to_dict() for nl in self.nodal_loads],
            "nodal_moments": [nm.to_dict() for nm in self.nodal_moments],
            "distributed_loads": [dl.to_dict() for dl in self.distributed_loads],
            "rotation_imperfections": [ri.id for ri in self.rotation_imperfections],
            "translation_imperfections": [ti.id for ti in self.translation_imperfections],
        }

    @staticmethod
    def apply_deadload_to_members(members, load_case, direction):
        """
        Apply a distributed load to all members

        Args:
            members (list): The list of members to search through.
            type (str): The type to search for in member.
            load_case (LoadCase): The load case to which the load belongs.
            magnitude (float): The magnitude of the load per unit length.
            direction (str): The direction of the load ('Y' for vertical loads, etc.).
            start_pos (float): The relative start position of the load along the member (0 = start, 1 = end).
            end_pos (float): The relative end position of the load along the member (0 = start, 1 = end).
        """
        from ..loads.distributedload import DistributedLoad

        for member in members:
            magnitude = -9.81 * member.weight
            DistributedLoad(
                member=member,
                load_case=load_case,
                magnitude=magnitude,
                direction=direction,
                start_pos=0,
                end_pos=1,
            )

    @staticmethod
    def apply_load_to_members_with_classification(
        members, classification, load_case, magnitude, direction, start_pos=0, end_pos=1
    ):
        """
        Apply a distributed load to members that match the given type.

        Args:
            members (list): The list of members to search through.
            type (str): The type to search for in member.
            load_case (LoadCase): The load case to which the load belongs.
            magnitude (float): The magnitude of the load per unit length.
            direction (str): The direction of the load ('Y' for vertical loads, etc.).
            start_pos (float): The relative start position of the load along the member (0 = start, 1 = end).
            end_pos (float): The relative end position of the load along the member (0 = start, 1 = end).
        """
        from ..loads.distributedload import DistributedLoad

        for member in members:
            if member.classification == classification:
                DistributedLoad(
                    member=member,
                    load_case=load_case,
                    magnitude=magnitude,
                    direction=direction,
                    start_pos=start_pos,
                    end_pos=end_pos,
                )
