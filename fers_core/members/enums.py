from enum import Enum


class MemberType(Enum):
    NORMAL = "Normal"
    TRUSS = "Truss"
    TENSION = "Tension"
    COMPRESSION = "Compression"
    RIGID = "Rigid"
