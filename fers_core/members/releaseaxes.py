from __future__ import annotations

from typing import Optional, Sequence, Union


class ReleaseAxes:
    """The axes a release names: what its ``_x``, ``_y`` and ``_z`` mean.

    - ``ReleaseAxes.LOCAL``: a member's own local axes.
    - ``ReleaseAxes.GLOBAL``: global X, Y and Z.
    - ``ReleaseAxes.user(x, y)``: a frame of your own, in global components. Its
      first axis runs along ``x``; its second along ``y``, made perpendicular to
      ``x``; its third is their cross product. A rack turned in plan names its
      own directions this way::

          from math import cos, radians, sin

          a = radians(30)
          along_the_rail = ReleaseAxes.user(x=(cos(a), 0.0, -sin(a)), y=(0.0, 1.0, 0.0))

    A :class:`ScissorHinge` releases in ``GLOBAL`` axes unless told otherwise;
    a :class:`MemberHinge` rotates in ``LOCAL`` ones. Release axes are fixed in
    space, so a corotational solve does not turn them with the structure.
    Requires ``fers_calculations >= 0.2.68``.
    """

    LOCAL: "ReleaseAxes"
    GLOBAL: "ReleaseAxes"

    def __init__(
        self,
        kind: str,
        x: Optional[Sequence[float]] = None,
        y: Optional[Sequence[float]] = None,
    ):
        if kind not in ("Local", "Global", "User"):
            raise ValueError(f"ReleaseAxes kind must be Local, Global or User, not {kind!r}")
        if kind == "User":
            if x is None or y is None or len(x) != 3 or len(y) != 3:
                raise ValueError("ReleaseAxes.user needs x and y, three components each")
            x, y = tuple(float(v) for v in x), tuple(float(v) for v in y)
        self.kind = kind
        self.x = x
        self.y = y

    @classmethod
    def user(cls, x: Sequence[float], y: Sequence[float]) -> "ReleaseAxes":
        return cls("User", x, y)

    def to_dict(self) -> Union[str, dict]:
        if self.kind == "User":
            return {"User": {"x": list(self.x), "y": list(self.y)}}
        return self.kind

    @classmethod
    def from_dict(cls, data: Union[str, dict, None], default: "ReleaseAxes") -> "ReleaseAxes":
        if data is None:
            return default
        if isinstance(data, str):
            return cls(data)
        user = data["User"]
        return cls.user(user["x"], user["y"])

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ReleaseAxes) and (self.kind, self.x, self.y) == (
            other.kind,
            other.x,
            other.y,
        )

    def __hash__(self) -> int:
        return hash((self.kind, self.x, self.y))

    def __repr__(self) -> str:
        if self.kind == "User":
            return f"ReleaseAxes.user(x={self.x}, y={self.y})"
        return f"ReleaseAxes.{self.kind.upper()}"


ReleaseAxes.LOCAL = ReleaseAxes("Local")
ReleaseAxes.GLOBAL = ReleaseAxes("Global")
