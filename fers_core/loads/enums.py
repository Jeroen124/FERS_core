from enum import Enum


class LimitState(Enum):
    ULS = "ULS"  # Ultimate Limit State
    SLS = "SLS"  # Serviceability Limit State
    FLS = "FLS"  # Fatigue Limit State
    ALS = "ALS"  # Accidental Limit State
