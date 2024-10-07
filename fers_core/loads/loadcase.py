from .lineload import LineLoad
from typing import Optional


class LoadCase:
    _load_case_counter = 1
    _all_load_cases = []

    def __init__(
        self,
        name: Optional[str] = None,
        load_case_id: Optional[int] = None,
        nodal_loads: Optional[list] = None,
        line_loads: Optional[list] = None,
        rotation_imperfections: Optional[list] = None,
        translation_imperfections: Optional[list] = None,
    ):
        if load_case_id is None:
            self.load_case_id = LoadCase._load_case_counter
            LoadCase._load_case_counter += 1
        else:
            self.load_case_id = load_case_id

        if name is None:
            self.name = f"Loadcase {self.load_case_id}"
        else:
            self.name = name

        self.nodal_loads = nodal_loads if nodal_loads is not None else []
        self.line_loads = line_loads if line_loads is not None else []
        self.rotation_imperfections = rotation_imperfections if rotation_imperfections is not None else []
        self.translation_imperfections = (
            translation_imperfections if translation_imperfections is not None else []
        )

        LoadCase._all_load_cases.append(self)

    def add_nodal_load(self, nodal_load):
        self.nodal_loads.append(nodal_load)

    def add_line_load(self, line_load):
        self.line_loads.append(line_load)

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

    @staticmethod
    def apply_deadload_to_members(members, load_case, direction):
        """
        Apply a line load to all members

        Args:
            members (list): The list of members to search through.
            type (str): The type to search for in member.
            load_case (LoadCase): The load case to which the load belongs.
            magnitude (float): The magnitude of the load per unit length.
            direction (str): The direction of the load ('Y' for vertical loads, etc.).
            start_pos (float): The relative start position of the load along the member (0 = start, 1 = end).
            end_pos (float): The relative end position of the load along the member (0 = start, 1 = end).
        """
        for member in members:
            magnitude = -9.81 * member.weight
            LineLoad(
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
        Apply a line load to members that match the given type.

        Args:
            members (list): The list of members to search through.
            type (str): The type to search for in member.
            load_case (LoadCase): The load case to which the load belongs.
            magnitude (float): The magnitude of the load per unit length.
            direction (str): The direction of the load ('Y' for vertical loads, etc.).
            start_pos (float): The relative start position of the load along the member (0 = start, 1 = end).
            end_pos (float): The relative end position of the load along the member (0 = start, 1 = end).
        """
        for member in members:
            if member.classification == classification:
                LineLoad(
                    member=member,
                    load_case=load_case,
                    magnitude=magnitude,
                    direction=direction,
                    start_pos=start_pos,
                    end_pos=end_pos,
                )
