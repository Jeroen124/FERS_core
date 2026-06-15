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
        surface_loads: Optional[list] = None,
        member_point_loads: Optional[list] = None,
        member_point_moments: Optional[list] = None,
        plate_pressures: Optional[list] = None,
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
        self.surface_loads = surface_loads if surface_loads is not None else []
        self.member_point_loads = member_point_loads if member_point_loads is not None else []
        self.member_point_moments = member_point_moments if member_point_moments is not None else []
        self.plate_pressures = plate_pressures if plate_pressures is not None else []

        LoadCase._all_load_cases.append(self)

    def add_nodal_load(self, nodal_load):
        self.nodal_loads.append(nodal_load)

    def add_nodal_moment(self, nodal_load):
        self.nodal_moments.append(nodal_load)

    def add_distributed_load(self, distributed_loads):
        self.distributed_loads.append(distributed_loads)

    def add_surface_load(self, surface_load):
        self.surface_loads.append(surface_load)

    def add_member_point_load(self, member_point_load):
        self.member_point_loads.append(member_point_load)

    def add_member_point_moment(self, member_point_moment):
        self.member_point_moments.append(member_point_moment)

    def add_plate_pressure(self, plate_pressure):
        self.plate_pressures.append(plate_pressure)

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
            "surface_loads": [sl.to_dict() for sl in self.surface_loads],
            "member_point_loads": [mpl.to_dict() for mpl in self.member_point_loads],
            "member_point_moments": [mpm.to_dict() for mpm in self.member_point_moments],
            "plate_pressures": [pp.to_dict() for pp in self.plate_pressures],
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
            "surface_loads": [ ... ],
            "sway_imperfections": [ids or dicts],
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
        from ..loads.surfaceload import SurfaceLoad
        from ..loads.memberpointload import MemberPointLoad
        from ..loads.memberpointmoment import MemberPointMoment
        from ..loads.platepressure import PlatePressure

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
            surface_loads=[],
        )

        # Ensure counter stays ahead of any explicit id
        if lc_id is not None and lc_id >= cls._load_case_counter:
            cls._load_case_counter = lc_id + 1

        # --- Nodal loads ---
        for nl_data in data.get("nodal_loads", []):
            NodalLoad.from_dict(nl_data, nodes=nodes, load_case=load_case)

        # --- Nodal moments ---
        for nm_data in data.get("nodal_moments", []):
            if isinstance(nm_data, dict):
                NodalMoment.from_dict(nm_data, nodes=nodes, load_case=load_case)

        # --- Distributed loads ---
        for dl_data in data.get("distributed_loads", []):
            if isinstance(dl_data, dict):
                if hasattr(DistributedLoad, "from_dict"):
                    DistributedLoad.from_dict(dl_data, members=members, load_case=load_case)
                else:
                    member_id = dl_data.get("member_id") or dl_data.get("member")
                    member = members.get(member_id)
                    kwargs = {
                        k: v
                        for k, v in dl_data.items()
                            if k not in {"id", "member", "member_id", "load_case"}
                    }
                    DistributedLoad(member=member, load_case=load_case, **kwargs)

        # --- Surface loads ---
        for sl_data in data.get("surface_loads", []):
            if isinstance(sl_data, dict):
                SurfaceLoad.from_dict(sl_data, load_case=load_case)

        # --- Member point loads ---
        for mpl_data in data.get("member_point_loads") or []:
            if isinstance(mpl_data, dict):
                MemberPointLoad.from_dict(mpl_data, members=members, load_case=load_case)

        # --- Member point moments ---
        for mpm_data in data.get("member_point_moments") or []:
            if isinstance(mpm_data, dict):
                MemberPointMoment.from_dict(mpm_data, members=members, load_case=load_case)

        # --- Plate pressures ---
        for pp_data in data.get("plate_pressures") or []:
            if isinstance(pp_data, dict):
                PlatePressure.from_dict(pp_data, load_case=load_case)

        # Imperfections are modeled via ImperfectionCase (analysis.imperfection_cases),
        # not on the load case — see imperfections/imperfectioncase.py.

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
