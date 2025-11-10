from typing import Optional, Dict, Any
from fers_core.nodes.node import Node
from fers_core.members.member import Member


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
        self.rotation_imperfections.append(rotation_imperfection)

    def add_translation_imperfection(self, translation_imperfection):
        self.translation_imperfections.append(translation_imperfection)

    @classmethod
    def reset_counter(cls):
        cls._load_case_counter = 1

    @classmethod
    def names(cls):
        return [lc.name for lc in cls._all_load_cases]

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

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        *,
        nodes: Optional[Dict[int, "Node"]] = None,
        members: Optional[Dict[int, "Member"]] = None,
    ) -> "LoadCase":
        """
        Rebuild a LoadCase from its dict representation.

        Expected structure (from to_dict()):
        {
            "id": int,
            "name": str,
            "nodal_loads": [ ... ],
            "nodal_moments": [ ... ],
            "distributed_loads": [ ... ],
            "rotation_imperfections": [ids or dicts],
            "translation_imperfections": [ids or dicts],
        }

        'nodes' and 'members' are lookup dicts (id -> instance) provided by FERS.from_dict.
        """
        from ..loads.nodalload import NodalLoad

        try:
            from ..loads.nodalmoment import NodalMoment
        except ImportError:  # if you don't have a separate class
            NodalMoment = NodalLoad  # type: ignore
        from ..loads.distributedload import DistributedLoad
        from ..imperfections.rotationimperfection import RotationImperfection
        from ..imperfections.translationimperfection import TranslationImperfection

        nodes = nodes or {}
        members = members or {}

        lc_id = data.get("id")
        name = data.get("name")

        # Create the base LoadCase (this also registers it in _all_load_cases)
        load_case = cls(
            name=name,
            id=lc_id,
            nodal_loads=[],
            nodal_moments=[],
            distributed_loads=[],
            rotation_imperfections=[],
            translation_imperfections=[],
        )

        # Ensure counter stays ahead of any explicit id
        if lc_id is not None and lc_id >= cls._load_case_counter:
            cls._load_case_counter = lc_id + 1

        # --- Nodal loads ---
        for nl_data in data.get("nodal_loads", []):
            nl = NodalLoad.from_dict(nl_data, nodes=nodes, load_case=load_case)

            load_case.add_nodal_load(nl)

        # --- Nodal moments ---
        for nm_data in data.get("nodal_moments", []):
            if isinstance(nm_data, dict):
                nm = NodalMoment.from_dict(nm_data, nodes=nodes, load_case=load_case)
                load_case.add_nodal_moment(nm)

        # --- Distributed loads ---
        for dl_data in data.get("distributed_loads", []):
            if isinstance(dl_data, dict):
                if hasattr(DistributedLoad, "from_dict"):
                    dl = DistributedLoad.from_dict(dl_data, members=members, load_case=load_case)
                else:
                    member_id = dl_data.get("member_id") or dl_data.get("member")
                    member = members.get(member_id)
                    kwargs = {
                        k: v
                        for k, v in dl_data.items()
                        if k not in {"id", "member", "member_id", "load_case"}
                    }
                    dl = DistributedLoad(member=member, load_case=load_case, **kwargs)
                load_case.add_distributed_load(dl)

        # --- Rotation imperfections (optional, usually handled via ImperfectionCase) ---
        for ri_data in data.get("rotation_imperfections", []):
            if isinstance(ri_data, dict):
                if hasattr(RotationImperfection, "from_dict"):
                    ri = RotationImperfection.from_dict(ri_data)
                else:
                    ri = RotationImperfection(**ri_data)
                load_case.rotation_imperfections.append(ri)
            else:
                # if it's just an id, keep it as a reference (link later if needed)
                load_case.rotation_imperfections.append(ri_data)

        # --- Translation imperfections ---
        for ti_data in data.get("translation_imperfections", []):
            if isinstance(ti_data, dict):
                if hasattr(TranslationImperfection, "from_dict"):
                    ti = TranslationImperfection.from_dict(ti_data)
                else:
                    ti = TranslationImperfection(**ti_data)
                load_case.translation_imperfections.append(ti)
            else:
                load_case.translation_imperfections.append(ti_data)

        return load_case

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
            start_frac (float): The relative start position of the load along the member (0 = start, 1 = end).
            end_frac (float): The relative end position of the load along the member (0 = start, 1 = end).
        """
        from ..loads.distributedload import DistributedLoad

        for member in members:
            magnitude = -9.81 * member.weight
            DistributedLoad(
                member=member,
                load_case=load_case,
                magnitude=magnitude,
                direction=direction,
                start_frac=0,
                end_frac=1,
            )

    @staticmethod
    def apply_load_to_members_with_classification(
        members, classification, load_case, magnitude, direction, start_frac=0, end_frac=1
    ):
        """
        Apply a distributed load to members that match the given type.

        Args:
            members (list): The list of members to search through.
            type (str): The type to search for in member.
            load_case (LoadCase): The load case to which the load belongs.
            magnitude (float): The magnitude of the load per unit length.
            direction (str): The direction of the load ('Y' for vertical loads, etc.).
            start_frac (float): The relative start position of the load along the member (0 = start, 1 = end).
            end_frac (float): The relative end position of the load along the member (0 = start, 1 = end).
        """
        from ..loads.distributedload import DistributedLoad

        for member in members:
            if member.classification == classification:
                DistributedLoad(
                    member=member,
                    load_case=load_case,
                    magnitude=magnitude,
                    direction=direction,
                    start_frac=start_frac,
                    end_frac=end_frac,
                )
