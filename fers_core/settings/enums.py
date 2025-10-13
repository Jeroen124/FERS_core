from enum import Enum


class AnalysisOrder(Enum):
    LINEAR = "LINEAR"
    NONLINEAR = "NONLINEAR"


class Dimensionality(Enum):
    TWO_DIMENSIONAL = "2D"
    THREE_DIMENSIONAL = "3D"
