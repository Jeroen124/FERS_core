from enum import Enum
from typing import Union


class MemberType(Enum):
    NORMAL = "Normal"
    TRUSS = "Truss"
    TENSION = "Tension"
    COMPRESSION = "Compression"
    RIGID = "Rigid"


def normalize_member_type(value: Union[MemberType, str]) -> MemberType:
    """
    Normalize a member type value to a MemberType enum.
    Accepts enum or string (case-insensitive).
    """
    if isinstance(value, MemberType):
        return value
    s = str(value).strip().lower()
    mapping = {
        "normal": MemberType.NORMAL,
        "truss": MemberType.TRUSS,
        "tension": MemberType.TENSION,
        "compression": MemberType.COMPRESSION,
        "rigid": MemberType.RIGID,
    }
    if s in mapping:
        return mapping[s]
    raise ValueError(
        f"Unknown member_type: {value!r}. Valid options are: "
        f"{', '.join(mapping.keys())} or MemberType values."
    )
