"""Ask the solver for only the results you read (engine >= 0.2.68).

``result_filter`` keeps or drops whole blocks. A ``ResultRequest`` names a block
and narrows it: to members (the unity checks' selectors) or nodes, to load
combinations by limit state or id, to components, and to one member end. The
solver returns what was asked for as dense arrays, and the SDK loads them into
the usual ``member_results``, ``displacement_nodes`` and ``reaction_nodes``;
anything not requested reads as ``None``, so a check that reads a value nobody
asked for fails instead of seeing a zero. The arrays themselves are on
``ResultsBundle.selections``.

Example::

    from fers_core import ResultBlock
    from fers_core.result_requests import ResultRequest, nodes_of
    from fers_core.unity_checks import classification

    uprights, beams = classification("Upright_1"), classification("beam")
    model.settings.analysis_options.result_requests = [
        ResultRequest(ResultBlock.LOCAL_ENVELOPES, members=[uprights, classification("Bracing")],
                      limit_state="ULS", components=["fx", "my", "mz"]),
        ResultRequest(ResultBlock.LOCAL_END_FORCES, members=beams, limit_state="ULS",
                      end="start", components=["my", "fz"]),
        ResultRequest(ResultBlock.NODE_DISPLACEMENTS, nodes=nodes_of(uprights, beams),
                      limit_state="SLS", components=["dx", "dy", "dz"]),
        ResultRequest(ResultBlock.REACTIONS, limit_state="ULS"),
    ]

Combinations are matched on their ``limit_state``, as unity checks match them:
set it on each ``LoadCombination`` to select by it. A request with neither a
limit state nor combination ids covers the load cases too. ``section_forces``
and ``internal_force_series`` cannot be requested, and ``result_requests``
cannot be combined with ``result_filter``; the solver refuses both before it
starts.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional, Union

from fers_core.loads.enums import LimitState
from fers_core.settings.enums import ResultBlock

Selector = Dict[str, Any]


def nodes(ids: Iterable[int]) -> Selector:
    """Select nodes by id, for ``node_displacements`` and ``reactions``."""
    return {"type": "Nodes", "ids": list(ids)}


def nodes_of(*members: Selector) -> Selector:
    """Select the start and end nodes of the members the member selectors pick."""
    return {"type": "NodesOfMembers", "members": list(members)}


def _wire(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


class ResultRequest:
    """One block of results to return; see the module docstring.

    Args:
        block: The block, as for ``result_filter``: ``LOCAL_ENVELOPES``,
            ``GLOBAL_ENVELOPES``, ``LOCAL_END_FORCES``, ``GLOBAL_END_FORCES``,
            ``LOCAL_DISPLACEMENTS`` (member blocks), or ``NODE_DISPLACEMENTS`` and
            ``REACTIONS`` (node blocks).
        members: For a member block, the members to return: one selector or a
            list, as unity checks take them (``classification``, ``members``,
            ``member_sets``, ``all_members``), combined as a union. All members
            when omitted.
        nodes: For a node block, ``nodes([...])`` or ``nodes_of(*selectors)``.
            All nodes when omitted.
        limit_state: Only the load combinations with this ``limit_state``.
        load_combination_ids: Only these load combinations. With neither filter,
            the load cases are returned too.
        components: Force components (``fx fy fz mx my mz bw``) or, for the
            displacement blocks, ``dx dy dz rx ry rz warp``. All when omitted.
        end: ``"start"`` or ``"end"``, for the end-force and end-displacement
            blocks. Both when omitted.
    """

    def __init__(
        self,
        block: Union[ResultBlock, str],
        members: Union[Selector, List[Selector], None] = None,
        nodes: Optional[Selector] = None,
        limit_state: Union[LimitState, str, None] = None,
        load_combination_ids: Optional[Iterable[int]] = None,
        components: Optional[Iterable[str]] = None,
        end: Optional[str] = None,
    ):
        self.block = block
        self.members = [members] if isinstance(members, Mapping) else list(members or [])
        self.nodes = nodes
        self.limit_state = limit_state
        self.load_combination_ids = list(load_combination_ids or [])
        self.components = [str(c).lower() for c in components or []]
        self.end = end

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {"block": _wire(self.block)}
        # Only what is set, as the solver writes it back.
        if self.members:
            data["members"] = [dict(m) for m in self.members]
        if self.nodes is not None:
            data["nodes"] = dict(self.nodes)
        if self.limit_state is not None:
            data["limit_state"] = _wire(self.limit_state)
        if self.load_combination_ids:
            data["load_combination_ids"] = list(self.load_combination_ids)
        if self.components:
            data["components"] = list(self.components)
        if self.end is not None:
            data["end"] = self.end
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ResultRequest":
        block = data["block"]
        known = {b.value: b for b in ResultBlock}
        return cls(
            block=known.get(block, block),
            members=list(data.get("members") or []),
            nodes=data.get("nodes"),
            limit_state=data.get("limit_state"),
            load_combination_ids=data.get("load_combination_ids"),
            components=data.get("components"),
            end=data.get("end"),
        )

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ResultRequest) and self.to_dict() == other.to_dict()

    def __repr__(self) -> str:
        return f"ResultRequest({self.to_dict()!r})"
