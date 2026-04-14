from __future__ import annotations

from typing import Optional

from ..supports.stiffness_curve import StiffnessCurveConfig


class MemberHinge:
    _hinge_counter = 1

    def __init__(
        self,
        id: int = None,
        hinge_type: str = "",
        translational_release_vx: float = None,
        translational_release_vy: float = None,
        translational_release_vz: float = None,
        rotational_release_mx: float = None,
        rotational_release_my: float = None,
        rotational_release_mz: float = None,
        rotational_release_warp: float = None,
        max_tension_vx: float = None,
        max_tension_vy: float = None,
        max_tension_vz: float = None,
        max_moment_mx: float = None,
        max_moment_my: float = None,
        max_moment_mz: float = None,
        max_bimoment_warp: float = None,
        stiffness_curve_vx: Optional[StiffnessCurveConfig] = None,
        stiffness_curve_vy: Optional[StiffnessCurveConfig] = None,
        stiffness_curve_vz: Optional[StiffnessCurveConfig] = None,
        stiffness_curve_mx: Optional[StiffnessCurveConfig] = None,
        stiffness_curve_my: Optional[StiffnessCurveConfig] = None,
        stiffness_curve_mz: Optional[StiffnessCurveConfig] = None,
    ):
        """Initialize a new Member Hinge instance.

        Supports translational/rotational releases, maximal tension/moment
        capacities, and optional non-linear stiffness curves per DOF.

        Args:
            translational_release_vx: Translational Spring Constant X.
            translational_release_vy: Translational Spring Constant Y.
            translational_release_vz: Translational Spring Constant Z.
            rotational_release_mx: Rotational Spring Constant X.
            rotational_release_my: Rotational Spring Constant Y.
            rotational_release_mz: Rotational Spring Constant Z.
            rotational_release_warp: Warping Spring Constant.
            max_tension_vx: Maximum Tension Capacity X.
            max_tension_vy: Maximum Tension Capacity Y.
            max_tension_vz: Maximum Tension Capacity Z.
            max_moment_mx: Maximum Moment Capacity X.
            max_moment_my: Maximum Moment Capacity Y.
            max_moment_mz: Maximum Moment Capacity Z.
            max_bimoment_warp: Maximum Bimoment Capacity (warping).
            stiffness_curve_vx: Non-linear stiffness curve for translational X.
            stiffness_curve_vy: Non-linear stiffness curve for translational Y.
            stiffness_curve_vz: Non-linear stiffness curve for translational Z.
            stiffness_curve_mx: Non-linear stiffness curve for rotational X.
            stiffness_curve_my: Non-linear stiffness curve for rotational Y.
            stiffness_curve_mz: Non-linear stiffness curve for rotational Z.
        """

        # Handle hinge numbering with an optional hinge_type
        if id is None:
            self.id = MemberHinge._hinge_counter
            MemberHinge._hinge_counter += 1
        else:
            self.id = id

        self.hinge_type = hinge_type
        self.translational_release_vx = translational_release_vx
        self.translational_release_vy = translational_release_vy
        self.translational_release_vz = translational_release_vz
        self.rotational_release_mx = rotational_release_mx
        self.rotational_release_my = rotational_release_my
        self.rotational_release_mz = rotational_release_mz
        self.rotational_release_warp = rotational_release_warp
        self.max_tension_vx = max_tension_vx
        self.max_tension_vy = max_tension_vy
        self.max_tension_vz = max_tension_vz
        self.max_moment_mx = max_moment_mx
        self.max_moment_my = max_moment_my
        self.max_moment_mz = max_moment_mz
        self.max_bimoment_warp = max_bimoment_warp
        self.stiffness_curve_vx = stiffness_curve_vx
        self.stiffness_curve_vy = stiffness_curve_vy
        self.stiffness_curve_vz = stiffness_curve_vz
        self.stiffness_curve_mx = stiffness_curve_mx
        self.stiffness_curve_my = stiffness_curve_my
        self.stiffness_curve_mz = stiffness_curve_mz

    @classmethod
    def reset_counter(cls):
        cls._hinge_counter = 1

    def to_dict(self):
        return {
            "id": self.id,
            "hinge_type": self.hinge_type,
            "translational_release_vx": self.translational_release_vx,
            "translational_release_vy": self.translational_release_vy,
            "translational_release_vz": self.translational_release_vz,
            "rotational_release_mx": self.rotational_release_mx,
            "rotational_release_my": self.rotational_release_my,
            "rotational_release_mz": self.rotational_release_mz,
            "rotational_release_warp": self.rotational_release_warp,
            "max_tension_vx": self.max_tension_vx,
            "max_tension_vy": self.max_tension_vy,
            "max_tension_vz": self.max_tension_vz,
            "max_moment_mx": self.max_moment_mx,
            "max_moment_my": self.max_moment_my,
            "max_moment_mz": self.max_moment_mz,
            "max_bimoment_warp": self.max_bimoment_warp,
            "stiffness_curve_vx": self.stiffness_curve_vx.to_dict() if self.stiffness_curve_vx else None,
            "stiffness_curve_vy": self.stiffness_curve_vy.to_dict() if self.stiffness_curve_vy else None,
            "stiffness_curve_vz": self.stiffness_curve_vz.to_dict() if self.stiffness_curve_vz else None,
            "stiffness_curve_mx": self.stiffness_curve_mx.to_dict() if self.stiffness_curve_mx else None,
            "stiffness_curve_my": self.stiffness_curve_my.to_dict() if self.stiffness_curve_my else None,
            "stiffness_curve_mz": self.stiffness_curve_mz.to_dict() if self.stiffness_curve_mz else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MemberHinge":
        return cls(
            id=data.get("id"),
            hinge_type=data.get("hinge_type", ""),
            translational_release_vx=data.get("translational_release_vx"),
            translational_release_vy=data.get("translational_release_vy"),
            translational_release_vz=data.get("translational_release_vz"),
            rotational_release_mx=data.get("rotational_release_mx"),
            rotational_release_my=data.get("rotational_release_my"),
            rotational_release_mz=data.get("rotational_release_mz"),
            rotational_release_warp=data.get("rotational_release_warp"),
            max_tension_vx=data.get("max_tension_vx"),
            max_tension_vy=data.get("max_tension_vy"),
            max_tension_vz=data.get("max_tension_vz"),
            max_moment_mx=data.get("max_moment_mx"),
            max_moment_my=data.get("max_moment_my"),
            max_moment_mz=data.get("max_moment_mz"),
            max_bimoment_warp=data.get("max_bimoment_warp"),
            stiffness_curve_vx=StiffnessCurveConfig.from_dict(data.get("stiffness_curve_vx")),
            stiffness_curve_vy=StiffnessCurveConfig.from_dict(data.get("stiffness_curve_vy")),
            stiffness_curve_vz=StiffnessCurveConfig.from_dict(data.get("stiffness_curve_vz")),
            stiffness_curve_mx=StiffnessCurveConfig.from_dict(data.get("stiffness_curve_mx")),
            stiffness_curve_my=StiffnessCurveConfig.from_dict(data.get("stiffness_curve_my")),
            stiffness_curve_mz=StiffnessCurveConfig.from_dict(data.get("stiffness_curve_mz")),
        )
