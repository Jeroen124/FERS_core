from typing import Any


class SwayImperfection:
    _sway_imperfection_counter = 1

    def __init__(
        self,
        magnitude: float,
        axis: tuple,
        height_direction: tuple = (0, 1, 0),
        reference_point: tuple = (0, 0, 0),
    ):
        """
        Initialize a geometric sway (out-of-plumb) imperfection.

        Applies to the whole model; which load combinations receive it is set on
        the owning ``ImperfectionCase``.

        Args:
            magnitude (float): The sway (lean) angle in radians, about ``axis``.
            axis (tuple): The rotation axis (e.g., (0, 0, 1) for the Z-axis). The
                sway direction is ``axis × height_direction``.
            height_direction (tuple): Direction height is measured along and which
                is never displaced (the structure's "up"). Defaults to (0, 1, 0).
            reference_point (tuple): A point on the zero-sway plane; the lean is
                proportional to a node's height above it. Defaults to (0, 0, 0).
        """
        self.magnitude = magnitude
        self.axis = axis
        self.height_direction = height_direction
        self.reference_point = reference_point

    def to_dict(self):
        return {
            "magnitude": self.magnitude,
            "axis": [self.axis[0], self.axis[1], self.axis[2]],
            "height_direction": [
                self.height_direction[0],
                self.height_direction[1],
                self.height_direction[2],
            ],
            "reference_point": [
                self.reference_point[0],
                self.reference_point[1],
                self.reference_point[2],
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SwayImperfection":
        """
        data schema (expected):
        {
            "magnitude": 0.005,
            "axis": [0, 0, 1],
            "height_direction": [0, 1, 0],   # optional, default [0, 1, 0]
            "reference_point": [0, 0, 0]      # optional, default [0, 0, 0]
        }

        Legacy keys (`memberset`/`memberset_ids`, `mode`, `axis_only`, `point`) are
        ignored; `point` is accepted as a fallback for `reference_point`.
        """

        def _as_vec(value, default):
            if value is None:
                return default
            return tuple(value) if isinstance(value, (list, tuple)) else tuple(float(x) for x in value)

        magnitude = float(data.get("magnitude", 0.0))
        axis = _as_vec(data.get("axis"), (0.0, 0.0, 1.0))
        height_direction = _as_vec(data.get("height_direction"), (0.0, 1.0, 0.0))
        reference_point = _as_vec(data.get("reference_point", data.get("point")), (0.0, 0.0, 0.0))

        return cls(
            magnitude=magnitude,
            axis=axis,
            height_direction=height_direction,
            reference_point=reference_point,
        )
