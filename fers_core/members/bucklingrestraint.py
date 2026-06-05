class BucklingRestraint:
    """A buckling restraint located at a node along a member set (one physical beam).

    Restraints are named by the local member axis they hold (not strong/weak,
    which depends on the section orientation). The spacing between consecutive
    restraint nodes yields the unrestrained length used for the corresponding
    buckling check; restraining twist gives a lateral-torsional restraint. The
    buckling-length computation itself is performed by the design-check layer;
    this class only carries the restraint definition through the model.
    """

    def __init__(
        self,
        node_id: int,
        restrains_local_y: bool = False,
        restrains_local_z: bool = False,
        restrains_torsion: bool = False,
    ):
        self.node_id = node_id
        self.restrains_local_y = restrains_local_y
        self.restrains_local_z = restrains_local_z
        self.restrains_torsion = restrains_torsion

    def to_dict(self):
        return {
            "node_id": self.node_id,
            "restrains_local_y": self.restrains_local_y,
            "restrains_local_z": self.restrains_local_z,
            "restrains_torsion": self.restrains_torsion,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BucklingRestraint":
        return cls(
            node_id=data["node_id"],
            restrains_local_y=data.get("restrains_local_y", False),
            restrains_local_z=data.get("restrains_local_z", False),
            restrains_torsion=data.get("restrains_torsion", False),
        )
