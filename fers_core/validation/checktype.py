from enum import Enum


class CheckType(Enum):
    GLOBAL_DEFLECTION = "global_deflection"
    LOCAL_DEFLECTION = "local_deflection"
    MAX_STRESS = "max_stress"  # Check if stress at any point exceeds yield strength
    MAX_STRAIN = "max_strain"  # Check if strain exceeds allowable limits
    BUCKLING = "buckling"  # Check if the structure is prone to buckling
    SHEAR_FORCE = "shear_force"  # Verify if shear force is within limits
    BENDING_MOMENT = "bending_moment"  # Ensure bending moment does not exceed capacity
    AXIAL_FORCE = "axial_force"  # Check axial force limits
    SUPPORT_REACTION = "support_reaction"  # Validate that reaction forces are correct
