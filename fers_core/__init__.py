from .nodes.node import Node
from .nodes.nodalmass import NodalMass
from .members.member import Member
from .members.enums import MemberType
from .fers.fers import FERS
from .members.material import Material, OrthotropicPlateMaterial
from .members.material_library import MaterialLibrary
from .members.section import Section
from .members.shapepath import ShapePath
from .members.memberset import MemberSet
from .members.bucklingrestraint import BucklingRestraint
from .supports.nodalsupport import NodalSupport
from .loads.loadcase import LoadCase
from .loads.loadcombination import LoadCombination
from .loads.nodalload import NodalLoad
from .loads.nodalmoment import NodalMoment
from .loads.distributedload import DistributedLoad
from .loads.surfaceload import SurfaceLoad, SurfaceLoadVertex
from .loads.memberpointload import MemberPointLoad
from .loads.memberpointmoment import MemberPointMoment
from .loads.platepressure import PlatePressure
from .plates.plate import Plate, PlateElement
from .plates.platesurface import PlateSurface, PlateVertex
from .plates.components import (
    PlateBehavior,
    PlateElementShape,
    PlateMeshSettings,
    PlateMeshDivisions,
    PlateMeshMethod,
    PlateOpening,
    PlateStiffnessModifiers,
    PlateTheory,
    PlaneState,
)
from .geometry.workaxis import WorkAxis
from .geometry.workplane import WorkPlane
from .entities.entitygroup import EntityGroup
from .imperfections.imperfectioncase import ImperfectionCase
from .imperfections.swayimperfection import SwayImperfection
from .imperfections.translationimperfection import TranslationImperfection
from .loads.distributionshape import DistributionShape
from .supports.supportcondition import SupportCondition
from .supports.supportcondition import SupportConditionType
from .supports.stiffness_curve import ForceComponent, StiffnessCurveConfig
from .settings.anlysis_options import (
    AnalysisOrder,
    Dimensionality,
    NonlinearMethod,
    PdeltaFormulation,
    PdeltaMode,
    RigidStrategy,
)
from .members.memberhinge import MemberHinge
from .results.resultsbundle import ResultsBundle
from .results.singleresults import SingleResults
from .results.member import MemberResult
from .results.nodes import NodeDisplacement, NodeForces, ReactionNodeResult
from .cloud import FersCloudClient
from .sections.steel_sections_en import resolve_section, list_sections
from .builders import create_beam, check_beam


def __getattr__(name: str):
    if name == "ModelRenderer":
        from .visualization.model_renderer import ModelRenderer
        globals()["ModelRenderer"] = ModelRenderer
        return ModelRenderer
    if name == "ResultRenderer":
        from .visualization.result_renderer import ResultRenderer
        globals()["ResultRenderer"] = ResultRenderer
        return ResultRenderer
    raise AttributeError(f"module 'fers_core' has no attribute {name!r}")


__all__ = [
    "AnalysisOrder",
    "Dimensionality",
    "DistributedLoad",
    "DistributionShape",
    "FERS",
    "FersCloudClient",
    "ForceComponent",
    "ImperfectionCase",
    "LoadCase",
    "LoadCombination",
    "Material",
    "OrthotropicPlateMaterial",
    "MaterialLibrary",
    "EntityGroup",
    "Member",
    "MemberType",
    "MemberHinge",
    "MemberPointLoad",
    "MemberPointMoment",
    "MemberResult",
    "MemberSet",
    "BucklingRestraint",
    "PlateElement",
    "PlatePressure",
    "PlateBehavior",
    "PlateElementShape",
    "PlateMeshSettings",
    "PlateMeshDivisions",
    "PlateMeshMethod",
    "PlateOpening",
    "PlateStiffnessModifiers",
    "PlateTheory",
    "PlaneState",
    "WorkAxis",
    "WorkPlane",
    "ModelRenderer",
    "Node",
    "NodalMass",
    "Plate",
    "PlateSurface",
    "PlateVertex",
    "NodeDisplacement",
    "NodeForces",
    "NodalLoad",
    "NodalMoment",
    "NodalSupport",
    "NonlinearMethod",
    "PdeltaFormulation",
    "PdeltaMode",
    "ReactionNodeResult",
    "ResultRenderer",
    "ResultsBundle",
    "RigidStrategy",
    "Section",
    "SurfaceLoad",
    "SurfaceLoadVertex",
    "list_sections",
    "resolve_section",
    "ShapePath",
    "SingleResults",
    "StiffnessCurveConfig",
    "SupportCondition",
    "SupportConditionType",
    "SwayImperfection",
    "TranslationImperfection",
    "check_beam",
    "create_beam",
]
