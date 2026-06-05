from typing import Any, Dict, List, Optional


class EntityGroup:
    """
    Generic, calculation-agnostic grouping of model entities for UI/visualization.

    Each ``*_ids`` list references model entities by id. All are optional.
    """

    _entity_group_counter = 1

    _ID_FIELDS = (
        "member_ids",
        "member_set_ids",
        "node_ids",
        "plate_surface_ids",
        "plate_element_ids",
        "support_ids",
        "work_axis_ids",
        "work_plane_ids",
    )

    def __init__(
        self,
        name: Optional[str] = None,
        member_ids: Optional[List[int]] = None,
        member_set_ids: Optional[List[int]] = None,
        node_ids: Optional[List[int]] = None,
        plate_surface_ids: Optional[List[int]] = None,
        plate_element_ids: Optional[List[int]] = None,
        support_ids: Optional[List[int]] = None,
        work_axis_ids: Optional[List[int]] = None,
        work_plane_ids: Optional[List[int]] = None,
        id: Optional[int] = None,
    ) -> None:
        self.id = id or EntityGroup._entity_group_counter
        if id is None:
            EntityGroup._entity_group_counter += 1
        self.name = name
        self.member_ids = member_ids
        self.member_set_ids = member_set_ids
        self.node_ids = node_ids
        self.plate_surface_ids = plate_surface_ids
        self.plate_element_ids = plate_element_ids
        self.support_ids = support_ids
        self.work_axis_ids = work_axis_ids
        self.work_plane_ids = work_plane_ids

    @classmethod
    def reset_counter(cls) -> None:
        cls._entity_group_counter = 1

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {"id": self.id, "name": self.name}
        for field in self._ID_FIELDS:
            data[field] = getattr(self, field)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EntityGroup":
        obj = cls(
            id=data.get("id"),
            name=data.get("name"),
            member_ids=data.get("member_ids"),
            member_set_ids=data.get("member_set_ids"),
            node_ids=data.get("node_ids"),
            plate_surface_ids=data.get("plate_surface_ids"),
            plate_element_ids=data.get("plate_element_ids"),
            support_ids=data.get("support_ids"),
            work_axis_ids=data.get("work_axis_ids"),
            work_plane_ids=data.get("work_plane_ids"),
        )
        if obj.id is not None and obj.id >= cls._entity_group_counter:
            cls._entity_group_counter = obj.id + 1
        return obj
