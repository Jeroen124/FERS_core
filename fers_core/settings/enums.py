from enum import Enum


class AnalysisOrder(Enum):
    LINEAR = "Linear"
    NONLINEAR = "Nonlinear"


class Dimensionality(Enum):
    TWO_DIMENSIONAL = "2D"
    THREE_DIMENSIONAL = "3D"
