class MemberHinge:
    _hinge_counter = 1

    def __init__(
        self,
        id: int = None,
        type: str = "",
        translational_release_vx: float = None,
        translational_release_vy: float = None,
        translational_release_vz: float = None,
        rotational_release_mx: float = None,
        rotational_release_my: float = None,
        rotational_release_mz: float = None,
        max_tension_vx: float = None,
        max_tension_vy: float = None,
        max_tension_vz: float = None,
        max_moment_mx: float = None,
        max_moment_my: float = None,
        max_moment_mz: float = None,
    ):
        """
        Initialize a new Member Hinge instance with optional parameters for
        translational and rotational releases, as well as maximal tension and moment
        capacities in each principal direction.

        Args:
            translational_release_vx (float, optional): Translational Spring Constant X.
            translational_release_vy (float, optional): Translational Spring Constant Y.
            translational_release_vz (float, optional): Translational Spring Constant Z.
            rotational_release_mx (float, optional): Rotational Spring Constant X.
            rotational_release_my (float, optional): Rotational Spring Constant Y.
            rotational_release_mz (float, optional): Rotational Spring Constant Z.
            max_tension_vx (float, optional): Maximum Tension Capacity X.
            max_tension_vy (float, optional): Maximum Tension Capacity Y.
            max_tension_vz (float, optional): Maximum Tension Capacity Z.
            max_moment_mx (float, optional): Maximum Moment Capacity X.
            max_moment_my (float, optional): Maximum Moment Capacity Y.
            max_moment_mz (float, optional): Maximum Moment Capacity Z.
        """

        # Handle hinge numbering with an optional type
        if id is None:
            self.id = MemberHinge._hinge_counter
            MemberHinge._hinge_counter += 1
        else:
            self.id = id

        self.type = type
        self.translational_release_vx = translational_release_vx
        self.translational_release_vy = translational_release_vy
        self.translational_release_vz = translational_release_vz
        self.rotational_release_mx = rotational_release_mx
        self.rotational_release_my = rotational_release_my
        self.rotational_release_mz = rotational_release_mz
        self.max_tension_vx = max_tension_vx
        self.max_tension_vy = max_tension_vy
        self.max_tension_vz = max_tension_vz
        self.max_moment_mx = max_moment_mx
        self.max_moment_my = max_moment_my
        self.max_moment_mz = max_moment_mz

    @classmethod
    def reset_counter(cls):
        cls._hinge_counter = 1

    def to_dict(self):
        return {
            "id": self.id,
            "type": self.type,
            "translational_release_vx": self.translational_release_vx,
            "translational_release_vy": self.translational_release_vy,
            "translational_release_vz": self.translational_release_vz,
            "rotational_release_mx": self.rotational_release_mx,
            "rotational_release_my": self.rotational_release_my,
            "rotational_release_mz": self.rotational_release_mz,
            "max_tension_vx": self.max_tension_vx,
            "max_tension_vy": self.max_tension_vy,
            "max_tension_vz": self.max_tension_vz,
            "max_moment_mx": self.max_moment_mx,
            "max_moment_my": self.max_moment_my,
            "max_moment_mz": self.max_moment_mz,
        }
