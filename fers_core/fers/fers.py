from __future__ import annotations

import re
from typing import Any, Optional, Tuple, Union, TYPE_CHECKING
import fers_calculations

if TYPE_CHECKING:
    from fers_core.cloud import FersCloudClient
    from fers_core.visualization.model_renderer import ModelRenderer
    from fers_core.visualization.result_renderer import ResultRenderer
import ujson

import numpy as np
import matplotlib.pyplot as plt

from fers_core.fers.deformation_utils import (
    centerline_path_points,
    extrude_along_path,
)
from fers_core.results.resultsbundle import ResultsBundle
from fers_core.supports.support_utils import (
    format_support_label,
    get_condition_type,
    color_for_condition_type,
    translational_summary,
)
from fers_core.types.list_utils import as_list

from ..imperfections.imperfectioncase import ImperfectionCase
from ..loads.loadcase import LoadCase
from ..loads.loadcombination import LoadCombination
from ..loads.nodalload import NodalLoad
from ..members.material import Material
from ..members.member import Member
from ..members.section import Section
from ..members.memberhinge import MemberHinge
from ..members.memberset import MemberSet
from ..members.shapepath import ShapePath
from ..nodes.node import Node
from ..supports.nodalsupport import NodalSupport
from ..settings.settings import Settings
from ..types.pydantic_models import ResultsBundle as ResultsBundleSchema


class FERS:
    def __init__(self, settings=None, reset_counters=True):
        if reset_counters:
            self.reset_counters()
        self.member_sets = []
        self.load_cases = []
        self.load_combinations = []
        self.imperfection_cases = []
        self.settings = (
            settings if settings is not None else Settings()
        )  # Use provided settings or create default
        self.validation_checks = []
        self.report = None
        self.resultsbundle = None

    def run_analysis_from_file(self, file_path: str):
        """
        Run the Rust-based FERS calculation from a file, validate the results using Pydantic,
        and update the FERS instance's results.

        Args:
            file_path (str): Path to the JSON input file.

        Raises:
            ValueError: If the validation of the results fails.
        """
        # Run the calculation
        try:
            print(f"Running analysis using {file_path}...")
            result_string = fers_calculations.calculate_from_file(file_path)
        except Exception as e:
            raise RuntimeError(f"Failed to run calculation: {e}")

        # Parse and validate the results
        try:
            results_dictionary = ujson.loads(result_string)
            results_bundle_dict = results_dictionary.get("results")
            if results_bundle_dict is None:
                raise ValueError("No 'results' field found in the calculation output")
            validated = ResultsBundleSchema(**results_bundle_dict)
            self.resultsbundle = ResultsBundle.from_pydantic(validated)
        except Exception as e:
            raise ValueError(f"Failed to parse or validate results: {e}")

    def run_analysis(self):
        """
        Run the Rust-based FERS calculation without saving the input to a file.
        The input JSON is generated directly from the current FERS instance.

        Args:
            calculation_module: Module to perform calculations (default is fers_calculations).

        Raises:
            ValueError: If the validation of the results fails.
        """

        # Generate the input JSON
        input_dict = self.to_dict()
        input_json = ujson.dumps(input_dict)

        # Run the calculation
        try:
            print("Running analysis with generated input JSON...")
            result_string = fers_calculations.calculate_from_json(input_json)
        except Exception as e:
            raise RuntimeError(f"Failed to run calculation: {e}")

        try:
            results_dictionary = ujson.loads(result_string)
            # Extract the 'results' field from the response
            results_bundle_dict = results_dictionary.get("results")
            if results_bundle_dict is None:
                raise ValueError("No 'results' field found in the calculation output")
            validated = ResultsBundleSchema(**results_bundle_dict)
            self.resultsbundle = ResultsBundle.from_pydantic(validated)
        except Exception as e:
            raise ValueError(f"Failed to parse or validate results: {e}")

    def to_dict(self, include_results: bool = True) -> dict[str, Any]:
        data: dict[str, Any] = {
            "member_sets": [member_set.to_dict() for member_set in self.member_sets],
            "load_cases": [load_case.to_dict() for load_case in self.load_cases],
            "load_combinations": [load_comb.to_dict() for load_comb in self.load_combinations],
            "imperfection_cases": [imp_case.to_dict() for imp_case in self.imperfection_cases],
            "settings": self.settings.to_dict(),
            "memberhinges": [
                hinge.to_dict() for hinge in self.get_unique_member_hinges_from_all_member_sets()
            ],
            "materials": [
                material.to_dict() for material in self.get_unique_materials_from_all_member_sets()
            ],
            "sections": [section.to_dict() for section in self.get_unique_sections_from_all_member_sets()],
            "nodal_supports": [ns.to_dict() for ns in self.get_unique_nodal_support_from_all_member_sets()],
            "shape_paths": [sp.to_dict() for sp in self.get_unique_shape_paths_from_all_member_sets()],
        }
        if include_results and self.resultsbundle is not None:
            data["resultsbundle"] = self.resultsbundle.to_dict()
        else:
            data["resultsbundle"] = None
        return data

    def settings_to_dict(self):
        """Convert settings to a dictionary representation with additional information."""
        return {
            **self.settings.to_dict(),
            "total_elements": self.number_of_elements(),
            "total_nodes": self.number_of_nodes(),
        }

    def save_to_json(self, file_path, indent=None):
        """Save the FERS model to a JSON file using ujson."""
        with open(file_path, "w") as json_file:
            ujson.dump(self.to_dict(), json_file, indent=indent)

    @classmethod
    def from_json(cls, file_path: str) -> "FERS":
        """
        Load a FERS model (including optional results) from a JSON file that was
        created with FERS.to_dict() / FERS.save_to_json().
        """
        with open(file_path, "r") as json_file:
            data = ujson.load(json_file)
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FERS":
        settings = Settings.from_dict(data["settings"])
        fers = cls(settings=settings, reset_counters=True)

        # lookup tables as you already have...
        id_to_shape_path = {
            sp_data["id"]: ShapePath.from_dict(sp_data)
            for sp_data in as_list(data.get("shape_paths"), "shape_paths")
        }

        id_to_material = {
            m_data["id"]: Material.from_dict(m_data) for m_data in as_list(data.get("materials"), "materials")
        }

        id_to_section = {}
        for s_data in as_list(data.get("sections"), "sections"):
            sec = Section.from_dict(s_data, materials_by_id=id_to_material, shapepaths_by_id=id_to_shape_path)
            id_to_section[sec.id] = sec

        id_to_support = {
            sup_data["id"]: NodalSupport.from_dict(sup_data)
            for sup_data in as_list(data.get("nodal_supports"), "nodal_supports")
        }

        id_to_hinge = {
            h_data["id"]: MemberHinge.from_dict(h_data)
            for h_data in as_list(data.get("memberhinges"), "memberhinges")
        }

        id_to_node: dict[int, Node] = {}
        id_to_member: dict[int, Member] = {}

        # member sets + members
        for ms_data in data.get("member_sets", []):
            members: list[Member] = []
            for m_data in ms_data.get("members", []):
                member = Member.from_dict(
                    m_data,
                    nodes_by_id=id_to_node,
                    nodal_supports_by_id=id_to_support,
                    sections_by_id=id_to_section,
                    hinges_by_id=id_to_hinge,
                    members_by_id=id_to_member,
                )
                members.append(member)

            ms_id = ms_data.get("id")
            member_set = MemberSet(
                members=members,
                classification=ms_data.get("classification"),
                l_y=ms_data.get("l_y"),
                l_z=ms_data.get("l_z"),
                id=ms_id,
            )
            fers.add_member_set(member_set)

        # NO second loop with resolve_member here. Delete that block.

        # load cases
        for lc_data in as_list(data.get("load_cases"), "load_cases"):
            lc = LoadCase.from_dict(lc_data, nodes=id_to_node, members=id_to_member)
            fers.add_load_case(lc)

        # load combinations
        for comb_data in as_list(data.get("load_combinations"), "load_combinations"):
            comb = LoadCombination.from_dict(comb_data, load_cases=fers.load_cases)
            fers.add_load_combination(comb)

        # Build membersets_by_id for imperfection cases
        membersets_by_id = {ms.id: ms for ms in fers.member_sets}

        # imperfection cases
        for imp_data in data.get("imperfection_cases", []):
            ic = ImperfectionCase.from_dict(
                imp_data, load_combinations=fers.load_combinations, membersets_by_id=membersets_by_id
            )
            fers.add_imperfection_case(ic)

        # results
        res_data = data.get("results")
        if res_data:
            validated = ResultsBundleSchema(**res_data)
            fers.resultsbundle = ResultsBundle.from_pydantic(validated)

        return fers

    def create_load_case(self, name):
        load_case = LoadCase(name=name)
        self.add_load_case(load_case)
        return load_case

    def create_load_combination(self, name, load_cases_factors, situation, check):
        load_combination = LoadCombination(
            name=name, load_cases_factors=load_cases_factors, situation=situation, check=check
        )
        self.add_load_combination(load_combination)
        return load_combination

    def create_imperfection_case(self, load_combinations):
        imperfection_case = ImperfectionCase(loadcombinations=load_combinations)
        self.add_imperfection_case(imperfection_case)
        return imperfection_case

    def add_load_case(self, load_case):
        self.load_cases.append(load_case)

    def add_load_combination(self, load_combination):
        self.load_combinations.append(load_combination)

    def add_member_set(self, *member_sets):
        for member_set in member_sets:
            self.member_sets.append(member_set)

    def add_imperfection_case(self, imperfection_case):
        self.imperfection_cases.append(imperfection_case)

    def number_of_elements(self):
        """Returns the total number of unique members in the model."""
        return len(self.get_all_members())

    def number_of_nodes(self):
        """Returns the total number of unique nodes in the model."""
        return len(self.get_all_nodes())

    def reset_counters(self):
        ImperfectionCase.reset_counter()
        LoadCase.reset_counter()
        LoadCombination.reset_counter()
        Member.reset_counter()
        MemberHinge.reset_counter()
        MemberSet.reset_counter()
        Node.reset_counter()
        NodalSupport.reset_counter()
        NodalLoad.reset_counter()
        Section.reset_counter()
        Material.reset_counter()
        ShapePath.reset_counter()

    @staticmethod
    def translate_member_set(member_set, translation_vector):
        """
        Translates a given member set by the specified vector.
        """
        new_members = []
        for member in member_set.members:
            new_start_node = Node(
                X=member.start_node.X + translation_vector[0],
                Y=member.start_node.Y + translation_vector[1],
                Z=member.start_node.Z + translation_vector[2],
                nodal_support=member.start_node.nodal_support,
            )
            new_end_node = Node(
                X=member.end_node.X + translation_vector[0],
                Y=member.end_node.Y + translation_vector[1],
                Z=member.end_node.Z + translation_vector[2],
                nodal_support=member.end_node.nodal_support,
            )
            new_member = Member(
                start_node=new_start_node,
                end_node=new_end_node,
                section=member.section,
                start_hinge=member.start_hinge,
                end_hinge=member.end_hinge,
                classification=member.classification,
                rotation_angle=member.rotation_angle,
                chi=member.chi,
                reference_member=member.reference_member,
                reference_node=member.reference_node,
                member_type=member.member_type,
            )
            new_members.append(new_member)
        return MemberSet(members=new_members, classification=member_set.classification)

    def create_combined_model_pattern(original_model, count, spacing_vector):
        """
        Creates a single model instance that contains the original model and additional
        replicated and translated member sets according to the specified pattern.

        Args:
            original_model (FERS): The original model to replicate.
            count (int): The number of times the model should be replicated, including the original.
            spacing_vector (tuple): A tuple (dx, dy, dz) representing the spacing between each model instance.

        Returns:
            FERS: A single model instance with combined member sets from the original and replicated models.
        """
        combined_model = FERS()
        node_mapping = {}
        member_mapping = {}

        for original_member_set in original_model.get_all_member_sets():
            combined_model.add_member_set(original_member_set)

        # Start replicating and translating the member sets
        for i in range(1, count):
            total_translation = (spacing_vector[0] * i, spacing_vector[1] * i, spacing_vector[2] * i)
            for original_node in original_model.get_all_nodes():
                # Translate node coordinates
                new_node_coords = (
                    original_node.X + total_translation[0],
                    original_node.Y + total_translation[1],
                    original_node.Z + total_translation[2],
                )
                # Create a new node or find an existing one with the same coordinates
                if new_node_coords not in node_mapping:
                    new_node = Node(
                        X=new_node_coords[0],
                        Y=new_node_coords[1],
                        Z=new_node_coords[2],
                        nodal_support=original_node.nodal_support,
                        classification=original_node.classification,
                    )
                    node_mapping[(original_node.id, i)] = new_node

        for i in range(1, count):
            for original_member_set in original_model.get_all_member_sets():
                new_members = []
                for member in original_member_set.members:
                    new_start_node = node_mapping[(member.start_node.id, i)]
                    new_end_node = node_mapping[(member.end_node.id, i)]
                    if member.reference_node is not None:
                        new_reference_node = node_mapping[(member.reference_node.id, i)]
                    else:
                        new_reference_node = None

                    new_member = Member(
                        start_node=new_start_node,
                        end_node=new_end_node,
                        section=member.section,
                        start_hinge=member.start_hinge,
                        end_hinge=member.end_hinge,
                        classification=member.classification,
                        rotation_angle=member.rotation_angle,
                        chi=member.chi,
                        reference_member=member.reference_member,
                        reference_node=new_reference_node,
                    )
                    new_members.append(new_member)
                    if member not in member_mapping:
                        member_mapping[member] = []
                    member_mapping[member].append(new_member)
                # Create and add the new member set to the combined model
                translated_member_set = MemberSet(
                    members=new_members,
                    classification=original_member_set.classification,
                    l_y=original_member_set.l_y,
                    l_z=original_member_set.l_z,
                )
                combined_model.add_member_set(translated_member_set)

        for new_member_lists in member_mapping.values():
            for new_member in new_member_lists:
                if new_member.reference_member:
                    # Find the new reference member corresponding to the original reference member
                    new_reference_member = member_mapping.get(new_member.reference_member, [None])[
                        0
                    ]  # Assuming a one-to-one mapping
                    new_member.reference_member = new_reference_member

        return combined_model

    def translate_model(model, translation_vector):
        """
        Creates a copy of the given model with all nodes translated by the specified vector.
        """
        new_model = FERS()
        node_translation_map = {}

        for original_node in model.get_all_nodes():
            translated_node = Node(
                X=original_node.X + translation_vector[0],
                Y=original_node.Y + translation_vector[1],
                Z=original_node.Z + translation_vector[2],
            )
            node_translation_map[original_node.id] = translated_node

        for original_member_set in model.get_all_member_sets():
            new_members = []
            for member in original_member_set.members:
                new_start_node = node_translation_map[member.start_node.id]
                new_end_node = node_translation_map[member.end_node.id]
                new_member = Member(
                    start_node=new_start_node,
                    end_node=new_end_node,
                    section=member.section,
                    start_hinge=member.start_hinge,
                    end_hinge=member.end_hinge,
                    classification=member.classification,
                    rotation_angle=member.rotation_angle,
                    chi=member.chi,
                    reference_member=member.reference_member,
                    reference_node=member.reference_node,
                    member_type=member.member_type,
                )
                new_members.append(new_member)
            new_member_set = MemberSet(
                members=new_members,
                classification=original_member_set.classification,
                id=original_member_set.id,
            )
            new_model.add_member_set(new_member_set)

        return new_model

    def get_structure_bounds(self):
        """
        Calculate the minimum and maximum coordinates of all nodes in the structure.

        Returns:
            tuple: A tuple ((min_x, min_y, min_z), (max_x, max_y, max_z)) representing
                the minimum and maximum coordinates of all nodes.
        """
        all_nodes = self.get_all_nodes()
        if not all_nodes:
            return None, None

        x_coords = [node.X for node in all_nodes]
        y_coords = [node.Y for node in all_nodes]
        z_coords = [node.Z for node in all_nodes]

        min_coords = (min(x_coords), min(y_coords), min(z_coords))
        max_coords = (max(x_coords), max(y_coords), max(z_coords))

        return min_coords, max_coords

    def get_all_load_cases(self):
        """Return all load cases in the model."""
        return self.load_cases

    def get_all_nodal_loads(self):
        """Return all nodal loads in the model."""
        nodal_loads = []
        for load_case in self.get_all_load_cases():
            nodal_loads.extend(load_case.nodal_loads)
        return nodal_loads

    def get_all_nodal_moments(self):
        """Return all nodal moments in the model."""
        nodal_moments = []
        for load_case in self.get_all_load_cases():
            nodal_moments.extend(load_case.nodal_moments)
        return nodal_moments

    def get_all_distributed_loads(self):
        """Return all line loads in the model."""
        distributed_loads = []
        for load_case in self.get_all_load_cases():
            distributed_loads.extend(load_case.distributed_loads)
        return distributed_loads

    def get_all_imperfection_cases(self):
        """Return all imperfection cases in the model."""
        return self.imperfection_cases

    def get_all_load_combinations(self):
        """Return all load combinations in the model."""
        return self.load_combinations

    def get_all_load_combinations_situations(self):
        return [load_combination.situation for load_combination in self.load_combinations]

    def get_all_member_sets(self):
        """Return all member sets in the model."""
        return self.member_sets

    @property
    def members(self) -> list:
        """All unique members in the model (property shorthand for get_all_members)."""
        return self.get_all_members()

    @property
    def nodes(self) -> list:
        """All unique nodes in the model (property shorthand for get_all_nodes)."""
        return self.get_all_nodes()

    def get_all_members(self):
        """Returns a list of all members in the model."""
        members = []
        member_ids = set()

        for member_set in self.member_sets:
            for member in member_set.members:
                if member.id not in member_ids:
                    members.append(member)
                    member_ids.add(member.id)

        return members

    def find_members_by_first_node(self, node):
        """
        Finds all members whose start node matches the given node.

        Args:
            node (Node): The node to search for at the start of members.

        Returns:
            List[Member]: A list of members starting with the given node.
        """
        matching_members = []
        for member in self.get_all_members():
            if member.start_node == node:
                matching_members.append(member)
        return matching_members

    def get_all_nodes(self):
        """Returns a list of all unique nodes in the model."""
        nodes = []
        node_ids = set()
        for member_set in self.member_sets:
            for member in member_set.members:
                if member.start_node.id not in node_ids:
                    nodes.append(member.start_node)
                    node_ids.add(member.start_node.id)

                if member.end_node.id not in node_ids:
                    nodes.append(member.end_node)
                    node_ids.add(member.end_node.id)

        return nodes

    def get_node_by_pk(self, pk):
        """Returns a node by its PK."""
        for node in self.get_all_nodes():
            if node.id == pk:
                return node
        return None

    def get_unique_materials_from_all_member_sets(self, ids_only: bool = False):
        """
        Collect unique materials used across all member sets. Ignores members without a section.
        Deduplicates by material.id.
        """
        by_id = {}
        for member_set in self.member_sets:
            materials = member_set.get_unique_materials(ids_only=False)
            for material in materials:
                if material is None:
                    continue
                by_id[material.id] = material
        return list(by_id.keys()) if ids_only else list(by_id.values())

    def get_unique_shape_paths_from_all_member_sets(self, ids_only: bool = False):
        """
        Collect unique ShapePath instances used across all member sets.
        Ignores members without a section or without a shape_path.
        """
        unique_shape_paths = {}
        for member_set in self.member_sets:
            for member in member_set.members:
                section = getattr(member, "section", None)
                if section is None or getattr(section, "shape_path", None) is None:
                    continue
                sp = section.shape_path
                if sp.id not in unique_shape_paths:
                    unique_shape_paths[sp.id] = sp
        return list(unique_shape_paths.keys()) if ids_only else list(unique_shape_paths.values())

    def get_unique_nodal_support_from_all_member_sets(self, ids_only=False):
        """
        Collects and returns unique NodalSupport instances used across all member sets in the model.

        Args:
            ids_only (bool): If True, return only the unique NodalSupport IDs.
                            Otherwise, return NodalSupport objects.

        Returns:
            list: List of unique NodalSupport instances or their IDs.
        """
        unique_nodal_supports = {}

        for member_set in self.member_sets:
            for member in member_set.members:
                # Check nodal supports for start and end nodes
                for node in [member.start_node, member.end_node]:
                    if node.nodal_support and node.nodal_support.id not in unique_nodal_supports:
                        # Store unique nodal supports by ID
                        unique_nodal_supports[node.nodal_support.id] = node.nodal_support

        # Return only the IDs if ids_only is True
        return list(unique_nodal_supports.keys()) if ids_only else list(unique_nodal_supports.values())

    def get_unique_sections_from_all_member_sets(self, ids_only: bool = False):
        """
        Collect unique sections used across all member sets. Ignores members without a section.
        Deduplicates by section.id.
        """
        by_id = {}
        for member_set in self.member_sets:
            sections = member_set.get_unique_sections(ids_only=False)
            for section in sections:
                if section is None:
                    continue
                by_id[section.id] = section
        return list(by_id.keys()) if ids_only else list(by_id.values())

    def get_unique_member_hinges_from_all_member_sets(self, ids_only: bool = False):
        """
        Collect unique member hinges used across all member sets.
        Deduplicates by hinge.id.
        """
        by_id = {}
        for member_set in self.member_sets:
            hinges = member_set.get_unique_memberhinges(ids_only=False)
            for hinge in hinges:
                if hinge is None:
                    continue
                by_id[hinge.id] = hinge
        return list(by_id.keys()) if ids_only else list(by_id.values())

    def get_unique_situations(self):
        """
        Returns a set of unique conditions used in the model, identified by their names.
        """
        unique_situations = set()
        for load_combination in self.load_combinations:
            if load_combination.situation:
                unique_situations.add(load_combination.situation)
        return unique_situations

    def get_unique_material_names(self):
        """Returns a set of unique material names used in the model (skips members without a section)."""
        unique_materials = set()
        for member_set in self.member_sets:
            for member in member_set.members:
                section = getattr(member, "section", None)
                if section is None or getattr(section, "material", None) is None:
                    continue
                unique_materials.add(section.material.name)
        return unique_materials

    def get_unique_section_names(self):
        """Returns a set of unique section names used in the model (skips members without a section)."""
        unique_sections = set()
        for member_set in self.member_sets:
            for member in member_set.members:
                section = getattr(member, "section", None)
                if section is None:
                    continue
                unique_sections.add(section.name)
        return unique_sections

    def get_all_unique_member_hinges(self):
        """Return all unique member hinge instances in the model."""
        unique_hinges = set()

        for member_set in self.member_sets:
            for member in member_set.members:
                # Check if the member has a start hinge and add it to the set if it does
                if member.start_hinge is not None:
                    unique_hinges.add(member.start_hinge)

                # Check if the member has an end hinge and add it to the set if it does
                if member.end_hinge is not None:
                    unique_hinges.add(member.end_hinge)

        return unique_hinges

    def get_load_case_by_name(self, name):
        """Retrieve a load case by its name."""
        for load_case in self.load_cases:
            if load_case.name == name:
                return load_case
        return None

    def get_membersets_by_classification(self, classification_pattern):
        if re.match(r"^\w+$", classification_pattern):
            matching_member_sets = [
                member_set
                for member_set in self.member_sets
                if classification_pattern in member_set.classification
            ]
        else:
            compiled_pattern = re.compile(classification_pattern)
            matching_member_sets = [
                member_set
                for member_set in self.member_sets
                if compiled_pattern.search(member_set.classification)
            ]
        return matching_member_sets

    def get_load_combination_by_name(self, name):
        """Retrieve the first load case by its name."""
        for load_combination in self.load_combinations:
            if load_combination.name == name:
                return load_combination
        return None

    def get_load_combination_by_pk(self, pk):
        """Retrieve a load case by its pk."""
        for load_combination in self.load_combinations:
            if load_combination.id == pk:
                return load_combination
        return None

    def plot_model_3d(
        self,
        show_nodes: bool = True,
        show_sections: bool = True,
        show_local_axes: bool = False,
        local_axes_at_midspan: bool = False,
        display_Local_axes_scale: float = 1.0,
        loadcase: Optional[str] = None,
        loadcombination: Optional[str] = None,
        display_load_scale: float = 1.0,
        show_load_labels: bool = True,
        show_supports: bool = True,
        show_support_labels: bool = True,
        support_size_fraction: float = 0.05,
        show_support_base_for_fixed: bool = True,
    ):
        """
        Creates an interactive 3D PyVista plot of the entire model, aligning
        sections to each member's axis.

        Parameters:
        - show_nodes: Whether to show node spheres.
        - show_sections: Whether to extrude sections along members' axes.
        - show_local_axes: Whether to plot local axes at each member.
        - local_axes_at_midspan: Draw local axes at midspan instead of start node.
        - display_Local_axes_scale: Scale for local axes arrows.
        - loadcase: Name of a single load case to display loads for.
        - loadcombination: Name of a load combination to display loads for.
          All contributing load cases are shown with their factors applied.
        - display_load_scale: Scale factor for point loads.
        - show_load_labels: Show load magnitudes next to arrows.
        - show_supports: Draw nodal supports visualization.
        - show_support_labels: Add compact text label per support (U[...] R[...]).
        - support_size_fraction: Size of support arrows vs model bounding size.
        - show_support_base_for_fixed: If True, draw a flat square (plate) for
        all-fixed translational supports.
        """
        import pyvista as pv

        # Build plot
        plotter = pv.Plotter()

        all_points = []
        all_lines = []
        offset = 0

        members = self.get_all_members()

        min_coords, max_coords = self.get_structure_bounds()
        if min_coords and max_coords:
            structure_size = np.linalg.norm(np.array(max_coords) - np.array(min_coords))
        else:
            structure_size = 1.0

        arrow_scale_for_loads = structure_size * 0.5
        support_arrow_scale = max(1e-6, structure_size * support_size_fraction)

        for m in members:
            s = m.start_node
            e = m.end_node
            all_points.append((s.X, s.Y, s.Z))
            all_points.append((e.X, e.Y, e.Z))
            all_lines.extend([2, offset, offset + 1])
            offset += 2

        all_points = np.array(all_points, dtype=np.float32)
        poly = pv.PolyData(all_points)
        poly.lines = np.array(all_lines, dtype=np.int32)
        plotter.add_mesh(poly, color="blue", line_width=2, label="Members")

        if show_sections:
            for m in members:
                s = m.start_node
                e = m.end_node
                sec = getattr(m, "section", None)
                if sec is None or getattr(sec, "shape_path", None) is None:
                    continue
                coords_2d, edges = sec.shape_path.get_shape_geometry()
                coords_local = np.array([[0.0, y, z] for y, z in coords_2d], dtype=np.float32)
                lx, ly, lz = m.local_coordinate_system()
                T = np.column_stack((lx, ly, lz))
                coords_g = coords_local @ T.T + np.array([s.X, s.Y, s.Z])
                pd = pv.PolyData(coords_g)
                line_arr = []
                for a, b in edges:
                    line_arr.extend((2, a, b))
                pd.lines = np.array(line_arr, dtype=np.int32)
                dx, dy, dz = e.X - s.X, e.Y - s.Y, e.Z - s.Z
                extr = pd.extrude([dx, dy, dz], capping=True)
                plotter.add_mesh(extr, color="steelblue", label=f"Section {sec.name}")

        if show_local_axes:
            for idx, m in enumerate(members):
                s = m.start_node
                e = m.end_node
                lx, ly, lz = m.local_coordinate_system()
                p0 = np.array([s.X, s.Y, s.Z], dtype=float)
                origin = 0.5 * (p0 + np.array([e.X, e.Y, e.Z], dtype=float)) if local_axes_at_midspan else p0
                sc = display_Local_axes_scale
                if idx == 0:
                    plotter.add_arrows(origin, lx * sc, color="red", label="Local X")
                    plotter.add_arrows(origin, ly * sc, color="green", label="Local Y")
                    plotter.add_arrows(origin, lz * sc, color="blue", label="Local Z")
                else:
                    plotter.add_arrows(origin, lx * sc, color="red")
                    plotter.add_arrows(origin, ly * sc, color="green")
                    plotter.add_arrows(origin, lz * sc, color="blue")

        # ── Collect load cases to render (with factors) ──────────────
        load_cases_to_render: list[tuple] = []  # [(LoadCase, factor), ...]
        if loadcombination:
            combo = self.get_load_combination_by_name(loadcombination)
            if combo:
                for lc_obj, factor in combo.load_cases_factors.items():
                    load_cases_to_render.append((lc_obj, factor))
            else:
                print(f"Warning: load combination '{loadcombination}' not found.")
        elif loadcase:
            lc = self.get_load_case_by_name(loadcase)
            if lc:
                load_cases_to_render.append((lc, 1.0))
            else:
                print(f"Warning: load case '{loadcase}' not found.")

        # ── Resolve units for load labels ────────────────────────
        _us = self.settings.unit_settings if self.settings else None
        _force_unit = getattr(_us, "force_unit", "N") if _us else "N"
        _length_unit = getattr(_us, "length_unit", "m") if _us else "m"
        _distributed_unit = f"{_force_unit}/{_length_unit}"

        # ── Helper: build meshes for one load case at a given scale ──
        def _build_load_meshes(lc, factor, scale, color):
            """Return list of (mesh_or_points, add_kwargs) tuples for one load case."""
            items = []  # [(pv_object, dict_of_add_mesh_kwargs), ...]

            # Nodal loads
            for nl in lc.nodal_loads:
                node = nl.node
                factored_mag = nl.magnitude * factor
                vec = np.array(nl.direction) * factored_mag * scale
                mag = np.linalg.norm(vec)
                if mag > 0:
                    direction = vec / mag
                    pos = np.array([node.X, node.Y, node.Z])
                    arrow_mesh = pv.Arrow(start=pos, direction=direction, scale=arrow_scale_for_loads)
                    items.append(("mesh", arrow_mesh, {"color": color, "line_width": 2}))
                    # Label at arrow midpoint
                    mid = pos + direction * (arrow_scale_for_loads / 2.0)
                    if show_load_labels:
                        items.append(("label", mid, f"{factored_mag:.2f} {_force_unit}", color))

            # Distributed loads
            for dl in lc.distributed_loads:
                member = dl.member
                start_node = member.start_node
                end_node = member.end_node
                member_vec = np.array(
                    [
                        end_node.X - start_node.X,
                        end_node.Y - start_node.Y,
                        end_node.Z - start_node.Z,
                    ]
                )
                member_length = np.linalg.norm(member_vec)
                if member_length < 1e-6:
                    continue

                factored_start_mag = dl.magnitude * factor
                factored_end_mag = dl.end_magnitude * factor
                start_pos = np.array([start_node.X, start_node.Y, start_node.Z]) + member_vec * dl.start_frac
                end_pos = np.array([start_node.X, start_node.Y, start_node.Z]) + member_vec * dl.end_frac
                num_arrows = max(3, int((dl.end_frac - dl.start_frac) * member_length / structure_size * 10))

                envelope_pts = []
                base_pts = []
                for i in range(num_arrows):
                    t = i / (num_arrows - 1) if num_arrows > 1 else 0.5
                    pos = start_pos + t * (end_pos - start_pos)
                    mag_at_pos = factored_start_mag + t * (factored_end_mag - factored_start_mag)
                    load_vec = np.array(dl.direction) * mag_at_pos * scale
                    load_mag = np.linalg.norm(load_vec)
                    if load_mag > 1e-6:
                        direction = load_vec / load_mag
                        al = arrow_scale_for_loads * 0.4
                        arrow = pv.Arrow(start=pos, direction=direction, scale=al)
                        items.append(("mesh", arrow, {"color": color}))
                        tip = pos + direction * al
                        envelope_pts.append(tip)
                        base_pts.append(pos)
                        # vertical connector
                        items.append(
                            ("mesh", pv.Line(pos, tip), {"color": color, "line_width": 1, "opacity": 0.6})
                        )

                if len(envelope_pts) > 1:
                    env_line = pv.lines_from_points(np.array(envelope_pts))
                    items.append(("mesh", env_line, {"color": color, "line_width": 3}))

                # label at midpoint
                if show_load_labels and num_arrows > 0:
                    mid_pos = (start_pos + end_pos) / 2.0
                    if abs(factored_start_mag - factored_end_mag) < 1e-6:
                        txt = f"{factored_start_mag:.2f} {_distributed_unit}"
                    else:
                        txt = f"{factored_start_mag:.2f} → {factored_end_mag:.2f} {_distributed_unit}"
                    items.append(("label", mid_pos, txt, color))

            return items

        # ── Add load case actors to the scene ────────────────────────
        _lc_colors = [
            "#FFA500",
            "#FF6B6B",
            "#4CAF50",
            "#2196F3",
            "#9C27B0",
            "#00BCD4",
            "#FF9800",
            "#E91E63",
            "#8BC34A",
            "#3F51B5",
            "#FFEB3B",
            "#795548",
            "#607D8B",
            "#FF5722",
            "#009688",
        ]

        # Track actors per load case for checkbox toggling
        lc_actor_groups: list[tuple[str, str, list]] = []  # [(name, color, [actors])]

        for lc_idx, (lc, factor) in enumerate(load_cases_to_render):
            color = _lc_colors[lc_idx % len(_lc_colors)]
            lc_name = f"{lc.name} (×{factor:.2g})" if len(load_cases_to_render) > 1 else lc.name
            items = _build_load_meshes(lc, factor, display_load_scale, color)
            actors = []
            for item in items:
                if item[0] == "mesh":
                    _, mesh_obj, kwargs = item
                    actor = plotter.add_mesh(mesh_obj, **kwargs)
                    actors.append(actor)
                elif item[0] == "label":
                    _, pos, txt, clr = item
                    actor = plotter.add_point_labels(
                        pos,
                        [txt],
                        font_size=12,
                        text_color=clr,
                        always_visible=show_load_labels,
                    )
                    actors.append(actor)
            lc_actor_groups.append((lc_name, color, actors))

        # ── Checkbox widgets to toggle each load case (top-left) ─────
        if len(lc_actor_groups) > 1:
            _win_w, _win_h = plotter.window_size
            for cb_idx, (lc_name, color, actors) in enumerate(lc_actor_groups):

                def _make_toggle(actor_list):
                    def toggle(flag):
                        for a in actor_list:
                            if hasattr(a, "SetVisibility"):
                                a.SetVisibility(flag)
                            # For label actors (vtkActor2D)
                            elif hasattr(a, "GetVisibility"):
                                a.SetVisibility(flag)
                        plotter.render()

                    return toggle

                _y = _win_h - 40 - cb_idx * 40
                plotter.add_checkbox_button_widget(
                    _make_toggle(actors),
                    value=True,
                    position=(10, _y),
                    size=30,
                    color_on=color,
                    color_off="grey",
                )
                # Label next to checkbox
                plotter.add_text(
                    lc_name,
                    position=(50, _y + 4),
                    font_size=9,
                    color=color,
                )

        if show_nodes:
            nodes = self.get_all_nodes()
            pts = np.array([(n.X, n.Y, n.Z) for n in nodes], dtype=np.float32)
            cloud = pv.PolyData(pts)
            glyph = cloud.glyph(
                geom=pv.Sphere(radius=max(1e-6, structure_size * 0.01)), scale=False, orient=False
            )
            plotter.add_mesh(glyph, color="red", label="Nodes")

        # Supports: arrows + optional square plate for all-fixed translations
        if show_supports:
            legend_types: set[str] = set()
            plate_legend_added = False
            axis_dirs = {
                "X": np.array([1.0, 0.0, 0.0]),
                "Y": np.array([0.0, 1.0, 0.0]),
                "Z": np.array([0.0, 0.0, 1.0]),
            }

            for node in self.get_all_nodes():
                sup = getattr(node, "nodal_support", None)
                if not sup:
                    continue

                pos = np.array([node.X, node.Y, node.Z], dtype=float)

                # Colored arrows by translational condition per axis
                for axis_name, axis_vec in axis_dirs.items():
                    ctype = get_condition_type(sup.displacement_conditions.get(axis_name))
                    color_val = color_for_condition_type(ctype)
                    label = None
                    # One legend item per condition type
                    if ctype not in legend_types:
                        label = f"Support {axis_name} – {ctype.title()}"
                        legend_types.add(ctype)
                    plotter.add_arrows(pos, axis_vec * support_arrow_scale, color=color_val, label=label)

                # Flat square plate if all three translations are fixed
                if show_support_base_for_fixed and translational_summary(sup) == "all_fixed":
                    plate_size = support_arrow_scale * 1.2  # edge length in X and Y
                    plate_thickness = support_arrow_scale * 0.15  # thin in Z to read as a square "plate"
                    # Square in the global XY plane (thin along Z)
                    plate = pv.Cube(
                        center=pos, x_length=plate_size, y_length=plate_size, z_length=plate_thickness
                    )
                    plotter.add_mesh(
                        plate,
                        color="black",
                        opacity=0.8,
                        label=None if plate_legend_added else "Fixed support (plate)",
                    )
                    plate_legend_added = True

                if show_support_labels:
                    text = format_support_label(sup)
                    label_pos = pos + np.array([1.0, 1.0, 1.0]) * (support_arrow_scale * 0.6)
                    plotter.add_point_labels(
                        label_pos, [text], font_size=12, text_color="black", always_visible=True
                    )

        plotter.add_legend(loc="lower right")

        min_coords, max_coords = self.get_structure_bounds()
        if min_coords and max_coords:
            margin = 0.5
            x_min, y_min, z_min = (c - margin for c in min_coords)
            x_max, y_max, z_max = (c + margin for c in max_coords)
            plotter.show_grid(bounds=[x_min, x_max, y_min, y_max, z_min, z_max], color="gray")
        else:
            plotter.show_grid(color="gray")

        plotter.show(title="FERS 3D Model")

    def plot_results_2d(
        self,
        *,
        plane: str = "yz",
        loadcase: Optional[Union[int, str]] = None,
        loadcombination: Optional[Union[int, str]] = None,
        # Deformation options (default: only deformations shown)
        show_deformations: bool = True,
        deformation_scale: float = 100.0,
        deformation_num_points: int = 41,
        show_original_shape: bool = True,
        original_line_width: float = 1.5,
        deformed_line_width: float = 2.0,
        original_color: str = "tab:blue",
        deformed_color: str = "tab:red",
        show_nodes: bool = True,
        node_point_size: int = 10,
        node_color: str = "black",
        show_supports: bool = False,  # keep False by default to keep the plot clean
        annotate_supports: bool = False,
        support_marker_size: int = 60,
        support_marker_edgecolor: str = "white",
        support_annotation_fontsize: int = 8,
        support_annotation_offset_xy: tuple[int, int] = (6, 6),
        # Local bending moment options (off by default)
        plot_local_bending_moment: Optional[str] = None,  # one of: None, "M_x", "M_y", "M_z"
        moment_num_points: int = 41,
        moment_scale: Optional[float] = None,  # None = auto scale based on structure size and maxima
        moment_diagram_style: str = "filled",  # "filled" or "line"
        moment_face_alpha: float = 0.35,
        # Axes and layout
        equal_aspect: bool = True,
        title: Optional[str] = None,
    ):
        """
        Show 2D results in a global projection plane ("xy", "xz", or "yz").

        Default behavior:
            - Plots only deformations (projected from 3D to the chosen plane).
            - Does not plot bending moments unless 'plot_local_bending_moment' is set.

        Notes:
            - Deformed centerlines are computed using 'centerline_path_points' in 3D,
            then projected to the chosen plane.
            - Local bending moments (M_x, M_y, M_z) are read from the results. The
            diagram is offset within the chosen plane, to the left of the projected
            member direction for positive values (classic 2D convention).
            - If a full curve (s vs M) is not available for a member, the method will
            fall back to a straight line between end moments when possible.
        """
        import numpy as np
        import matplotlib.pyplot as plt

        if self.resultsbundle is None:
            raise ValueError("No analysis results available. Run an analysis first.")

        if loadcase is not None and loadcombination is not None:
            raise ValueError("Specify either 'loadcase' OR 'loadcombination', not both.")

        # Select which result set to show
        if loadcase is not None:
            loadcase_keys = list(self.resultsbundle.loadcases.keys())
            if isinstance(loadcase, int):
                if loadcase < 1 or loadcase > len(loadcase_keys):
                    raise IndexError(f"Loadcase index {loadcase} is out of range.")
                selected_key = loadcase_keys[loadcase - 1]
            else:
                selected_key = str(loadcase)
                if selected_key not in self.resultsbundle.loadcases:
                    available_loadcases = [
                        f"'{v.name}'" if getattr(v, "name", None) else f"'{k}'"
                        for k, v in self.resultsbundle.loadcases.items()
                    ]
                    raise KeyError(
                        f"Loadcase '{selected_key}' not found. "
                        f"Available loadcases: {', '.join(available_loadcases)}"
                    )
            chosen_results = self.resultsbundle.loadcases[selected_key]
            chosen_title = chosen_results.name if hasattr(chosen_results, "name") else str(selected_key)
        elif loadcombination is not None:
            loadcomb_keys = list(self.resultsbundle.loadcombinations.keys())
            if isinstance(loadcombination, int):
                if loadcombination < 1 or loadcombination > len(loadcomb_keys):
                    raise IndexError(f"Loadcombination index {loadcombination} is out of range.")
                selected_key = loadcomb_keys[loadcombination - 1]
            else:
                selected_key = str(loadcombination)
                if selected_key not in self.resultsbundle.loadcombinations:
                    available_combinations = [
                        f"'{v.name}'" if getattr(v, "name", None) else f"'{k}'"
                        for k, v in self.resultsbundle.loadcombinations.items()
                    ]
                    raise KeyError(
                        f"Loadcombination '{selected_key}' not found. "
                        f"Available loadcombinations: {', '.join(available_combinations) or 'none'}"
                    )
            chosen_results = self.resultsbundle.loadcombinations[selected_key]
            chosen_title = chosen_results.name if hasattr(chosen_results, "name") else str(selected_key)
        else:
            if len(self.resultsbundle.loadcases) == 1 and not self.resultsbundle.loadcombinations:
                chosen_results = next(iter(self.resultsbundle.loadcases.values()))
                chosen_title = chosen_results.name if hasattr(chosen_results, "name") else "Loadcase"
            else:
                raise ValueError("Multiple results available. Specify 'loadcase' or 'loadcombination'.")

        # Plane helpers
        def project_xyz_to_plane(
            x_value: float, y_value: float, z_value: float, plane_name: str
        ) -> tuple[float, float]:
            lower = plane_name.lower()
            if lower == "xy":
                return x_value, y_value
            if lower == "xz":
                return x_value, z_value
            if lower == "yz":
                return y_value, z_value
            raise ValueError("plane must be one of 'xy', 'xz', or 'yz'")

        def axis_labels_for_plane(plane_name: str) -> tuple[str, str]:
            lower = plane_name.lower()
            if lower == "xy":
                return "X", "Y"
            if lower == "xz":
                return "X", "Z"
            if lower == "yz":
                return "Y", "Z"
            raise ValueError("plane must be one of 'xy', 'xz', or 'yz'")

        # Result field helpers (aligns with your 3D method)
        def normalize_key(name: str) -> str:
            return name.lower().replace("_", "")

        def get_component(container_or_object, requested_name: str):
            if container_or_object is None:
                return None
            candidates = [
                requested_name,
                requested_name.replace("_", ""),
                requested_name.lower(),
                requested_name.upper(),
                requested_name.capitalize(),
                requested_name.replace("_", "").lower(),
            ]
            for candidate in candidates:
                if hasattr(container_or_object, candidate):
                    return getattr(container_or_object, candidate)
            if isinstance(container_or_object, dict):
                for candidate in candidates:
                    if candidate in container_or_object:
                        return container_or_object[candidate]
                for key, value in container_or_object.items():
                    if normalize_key(key) == normalize_key(requested_name):
                        return value
            return None

        def fetch_member_curve(
            member_identifier: int, component_name: str
        ) -> Optional[tuple[np.ndarray, np.ndarray]]:
            # Preferred containers that hold s and M arrays
            for attribute_name in [
                "internal_forces_by_member",
                "member_internal_forces",
                "line_forces_by_member",
                "member_line_forces",
                "element_forces_by_member",
            ]:
                container = getattr(chosen_results, attribute_name, None)
                if container and str(member_identifier) in container:
                    record = container[str(member_identifier)]
                    if isinstance(record, dict):
                        s_values = get_component(record, "s")
                        m_values = get_component(record, component_name)
                        if s_values is not None and m_values is not None:
                            s_values = np.asarray(s_values, dtype=float)
                            m_values = np.asarray(m_values, dtype=float)
                            if s_values.size > 1 and s_values.size == m_values.size:
                                return s_values, m_values

            # Nested under members
            members_map = getattr(chosen_results, "members", None)
            if members_map and str(member_identifier) in members_map:
                member_object = members_map[str(member_identifier)]
                for nested_name in ["internal_forces", "line_forces"]:
                    nested = getattr(member_object, nested_name, None)
                    if nested is not None:
                        s_values = get_component(nested, "s")
                        m_values = get_component(nested, component_name)
                        if s_values is not None and m_values is not None:
                            s_values = np.asarray(s_values, dtype=float)
                            m_values = np.asarray(m_values, dtype=float)
                            if s_values.size > 1 and s_values.size == m_values.size:
                                return s_values, m_values
            return None

        def fetch_member_end_forces(
            member_identifier: int, component_name: str
        ) -> Optional[tuple[np.ndarray, np.ndarray]]:
            # Your primary layout
            container = getattr(chosen_results, "member_results", None)
            if container and str(member_identifier) in container:
                record = container[str(member_identifier)]
                start_forces = (
                    getattr(record, "start_node_forces", None)
                    or getattr(record, "start", None)
                    or getattr(record, "i", None)
                )
                end_forces = (
                    getattr(record, "end_node_forces", None)
                    or getattr(record, "end", None)
                    or getattr(record, "j", None)
                )
                start_value = get_component(start_forces, component_name)
                end_value = get_component(end_forces, component_name)
                if start_value is not None and end_value is not None:
                    return np.array([0.0, 1.0], dtype=float), np.array(
                        [float(start_value), float(end_value)], dtype=float
                    )

            # Other fallback containers
            for attribute_name in [
                "member_end_forces",
                "end_forces_by_member",
                "member_forces",
                "element_forces",
                "elements_end_forces",
            ]:
                container = getattr(chosen_results, attribute_name, None)
                if container and str(member_identifier) in container:
                    record = container[str(member_identifier)]
                    if isinstance(record, dict):
                        start = (
                            record.get("start")
                            or record.get("i")
                            or record.get("node_i")
                            or record.get("end_i")
                        )
                        end = (
                            record.get("end")
                            or record.get("j")
                            or record.get("node_j")
                            or record.get("end_j")
                        )
                        start_value = get_component(start, component_name)
                        end_value = get_component(end, component_name)
                        if start_value is None:
                            for key, value in record.items():
                                if normalize_key(key).startswith(
                                    normalize_key(component_name)
                                ) and normalize_key(key).endswith("i"):
                                    start_value = float(value)
                                if normalize_key(key).startswith(
                                    normalize_key(component_name)
                                ) and normalize_key(key).endswith("j"):
                                    end_value = float(value)
                        if start_value is not None and end_value is not None:
                            return np.array([0.0, 1.0], dtype=float), np.array(
                                [float(start_value), float(end_value)], dtype=float
                            )
            return None

        def resample_to(num_samples: int, s_values: np.ndarray, y_values: np.ndarray) -> np.ndarray:
            s_target = np.linspace(0.0, 1.0, num=num_samples)
            return np.interp(s_target, s_values, y_values)

        # Gather node displacements (for deformed centerlines)
        need_displacements = show_deformations or (plot_local_bending_moment is not None)
        node_displacements: dict[int, Tuple[np.ndarray, np.ndarray]] = {}
        if need_displacements:
            displacement_nodes = getattr(chosen_results, "displacement_nodes", {}) or {}
            for node_id_string, disp in displacement_nodes.items():
                node_id = int(node_id_string)
                node_object = self.get_node_by_pk(node_id)
                if node_object is None:
                    continue
                if disp:
                    displacement_global = np.array([disp.dx, disp.dy, disp.dz], dtype=float)
                    rotation_global = np.array([disp.rx, disp.ry, disp.rz], dtype=float)
                else:
                    displacement_global = np.zeros(3, dtype=float)
                    rotation_global = np.zeros(3, dtype=float)
                node_displacements[node_id] = (displacement_global, rotation_global)

        # Prepare plotting

        figure, axes = plt.subplots()
        x_label, y_label = axis_labels_for_plane(plane)
        axes.set_xlabel(x_label)
        axes.set_ylabel(y_label)

        # Compute structure span in the plotted plane for auto scaling
        min_coords, max_coords = self.get_structure_bounds()
        if min_coords is not None and max_coords is not None:
            if plane.lower() == "xy":
                span_x = max(1e-9, max_coords[0] - min_coords[0])
                span_y = max(1e-9, max_coords[1] - min_coords[1])
            elif plane.lower() == "xz":
                span_x = max(1e-9, max_coords[0] - min_coords[0])
                span_y = max(1e-9, max_coords[2] - min_coords[2])
            else:  # "yz"
                span_x = max(1e-9, max_coords[1] - min_coords[1])
                span_y = max(1e-9, max_coords[2] - min_coords[2])
            structure_span_in_plane = float(np.hypot(span_x, span_y))
        else:
            structure_span_in_plane = 1.0

        # Draw original and deformed centerlines
        if show_original_shape or show_deformations:
            for member in self.get_all_members():
                start_displacement, start_rotation = node_displacements.get(
                    member.start_node.id, (np.zeros(3), np.zeros(3))
                )
                end_displacement, end_rotation = node_displacements.get(
                    member.end_node.id, (np.zeros(3), np.zeros(3))
                )

                # Compute original and deformed 3D polylines along the centerline
                original_curve_3d, deformed_curve_3d = centerline_path_points(
                    member,
                    start_displacement,
                    start_rotation,
                    end_displacement,
                    end_rotation,
                    max(2, deformation_num_points),
                    deformation_scale,
                )

                # Project to the selected plane
                original_xy = np.array(
                    [project_xyz_to_plane(p[0], p[1], p[2], plane) for p in original_curve_3d], dtype=float
                )
                deformed_xy = np.array(
                    [project_xyz_to_plane(p[0], p[1], p[2], plane) for p in deformed_curve_3d], dtype=float
                )

                if show_original_shape:
                    axes.plot(
                        original_xy[:, 0],
                        original_xy[:, 1],
                        color=original_color,
                        linewidth=original_line_width,
                        zorder=1,
                        label="Original Shape" if member == self.get_all_members()[0] else None,
                    )

                if show_deformations:
                    axes.plot(
                        deformed_xy[:, 0],
                        deformed_xy[:, 1],
                        color=deformed_color,
                        linewidth=deformed_line_width,
                        zorder=2,
                        label="Deformed Shape" if member == self.get_all_members()[0] else None,
                    )

        # Optional: draw nodes
        if show_nodes:
            node_points_projected = [project_xyz_to_plane(n.X, n.Y, n.Z, plane) for n in self.get_all_nodes()]
            if node_points_projected:
                axes.scatter(
                    [p[0] for p in node_points_projected],
                    [p[1] for p in node_points_projected],
                    s=node_point_size,
                    c=node_color,
                    zorder=5,
                    edgecolors="none",
                    label="Nodes",
                )

        # Optional: draw supports in 2D (very compact, plane-aware)
        if show_supports:
            from fers_core.supports.support_utils import (
                get_condition_type,
                color_for_condition_type,
                format_support_short,
            )

            def in_plane_axes(plane_name: str) -> tuple[str, str]:
                lower = plane_name.lower()
                if lower == "xy":
                    return "X", "Y"
                if lower == "xz":
                    return "X", "Z"
                if lower == "yz":
                    return "Y", "Z"
                raise ValueError("plane must be one of 'xy', 'xz', 'yz'")

            def marker_for_support_on_plane(nodal_support, plane_name: str) -> str:
                axis_one, axis_two = in_plane_axes(plane_name)
                cond_one = get_condition_type((nodal_support.displacement_conditions or {}).get(axis_one))
                cond_two = get_condition_type((nodal_support.displacement_conditions or {}).get(axis_two))
                if cond_one == "fixed" and cond_two == "fixed":
                    return "s"
                if cond_one == "fixed" and cond_two != "fixed":
                    return "|"
                if cond_two == "fixed" and cond_one != "fixed":
                    return "_"
                if cond_one == "spring" or cond_two == "spring":
                    return "D"
                return "o"

            plotted_legend = False
            for node in self.get_all_nodes():
                support = getattr(node, "nodal_support", None)
                if not support:
                    continue
                px, py = project_xyz_to_plane(node.X, node.Y, node.Z, plane)
                face_color = color_for_condition_type(
                    "fixed" if marker_for_support_on_plane(support, plane) in ("s", "|", "_") else "mixed"
                )
                axes.scatter(
                    [px],
                    [py],
                    s=support_marker_size,
                    marker=marker_for_support_on_plane(support, plane),
                    c=face_color,
                    edgecolors=support_marker_edgecolor,
                    linewidths=0.5,
                    zorder=6,
                    label="Supports" if not plotted_legend else None,
                )
                plotted_legend = True
                if annotate_supports:
                    axes.annotate(
                        format_support_short(support),
                        (px, py),
                        textcoords="offset points",
                        xytext=support_annotation_offset_xy,
                        fontsize=support_annotation_fontsize,
                        color="black",
                        zorder=7,
                    )

        # Optional: local bending moment diagrams in the 2D plane

        if plot_local_bending_moment is not None:
            requested_component = str(plot_local_bending_moment)
            all_moment_arrays_abs_maxima: list[float] = []
            per_member_plot_items: list[dict] = []

            for member in self.get_all_members():
                # Try to obtain a curve; otherwise use end forces; otherwise skip
                curve = fetch_member_curve(member.id, requested_component)
                if curve is None:
                    curve = fetch_member_end_forces(member.id, requested_component)
                if curve is None:
                    continue

                s_values_raw, moment_values_raw = curve
                moment_values = resample_to(
                    moment_num_points, np.asarray(s_values_raw, float), np.asarray(moment_values_raw, float)
                )

                # Baseline points along the member projected to the plane
                start_point_projected = project_xyz_to_plane(
                    member.start_node.X, member.start_node.Y, member.start_node.Z, plane
                )
                end_point_projected = project_xyz_to_plane(
                    member.end_node.X, member.end_node.Y, member.end_node.Z, plane
                )
                parameter = np.linspace(0.0, 1.0, moment_num_points)
                baseline_x = start_point_projected[0] * (1.0 - parameter) + end_point_projected[0] * parameter
                baseline_y = start_point_projected[1] * (1.0 - parameter) + end_point_projected[1] * parameter

                # In-plane left normal for positive offset
                delta_x = end_point_projected[0] - start_point_projected[0]
                delta_y = end_point_projected[1] - start_point_projected[1]
                member_length_in_plane = float(np.hypot(delta_x, delta_y)) or 1.0
                tangent_x = delta_x / member_length_in_plane
                tangent_y = delta_y / member_length_in_plane
                normal_x = -tangent_y
                normal_y = tangent_x

                per_member_plot_items.append(
                    {
                        "baseline_x": baseline_x,
                        "baseline_y": baseline_y,
                        "normal_x": normal_x,
                        "normal_y": normal_y,
                        "moment_values": moment_values,
                    }
                )
                all_moment_arrays_abs_maxima.append(
                    float(np.max(np.abs(moment_values))) if moment_values.size else 0.0
                )

            if per_member_plot_items:
                global_abs_max_moment = max(all_moment_arrays_abs_maxima) or 1.0
                effective_moment_scale = (
                    moment_scale
                    if (moment_scale is not None and moment_scale > 0.0)
                    else (0.08 * structure_span_in_plane / global_abs_max_moment)
                )

                for item in per_member_plot_items:
                    baseline_x = item["baseline_x"]
                    baseline_y = item["baseline_y"]
                    normal_x = item["normal_x"]
                    normal_y = item["normal_y"]
                    moment_values = item["moment_values"]

                    offset_x = baseline_x + effective_moment_scale * moment_values * normal_x
                    offset_y = baseline_y + effective_moment_scale * moment_values * normal_y

                    if moment_diagram_style.lower() == "filled":
                        axes.fill_between(
                            baseline_x,
                            baseline_y,
                            offset_y,
                            alpha=moment_face_alpha,
                            edgecolor="none",
                            zorder=4,
                        )
                        axes.plot(offset_x, offset_y, linewidth=1.0, color="black", zorder=5)
                    else:
                        axes.plot(offset_x, offset_y, linewidth=2.0, color="black", zorder=5)

        # Final formatting
        if min_coords is not None and max_coords is not None:
            if plane.lower() == "xy":
                min_x, max_x = min_coords[0], max_coords[0]
                min_y, max_y = min_coords[1], max_coords[1]
            elif plane.lower() == "xz":
                min_x, max_x = min_coords[0], max_coords[0]
                min_y, max_y = min_coords[2], max_coords[2]
            else:  # "yz"
                min_x, max_x = min_coords[1], max_coords[1]
                min_y, max_y = min_coords[2], max_coords[2]
            span_x = max(1e-9, max_x - min_x)
            span_y = max(1e-9, max_y - min_y)
            margin_x = 0.04 * span_x
            margin_y = 0.04 * span_y
            axes.set_xlim(min_x - margin_x, max_x + margin_x)
            axes.set_ylim(min_y - margin_y, max_y + margin_y)

        if equal_aspect:
            axes.set_aspect("equal", adjustable="box")

        legend_needed = show_original_shape or show_deformations or show_nodes or show_supports
        if legend_needed:
            axes.legend(loc="best")

        final_title = title if title is not None else f"Results 2D – {chosen_title} ({plane.upper()} view)"
        axes.set_title(final_title)
        figure.tight_layout()
        plt.show()

    def plot_results_3d(
        self,
        *,
        loadcase: Optional[Union[int, str]] = None,
        loadcombination: Optional[Union[int, str]] = None,
        show_nodes: bool = True,
        show_sections: bool = True,
        displacement: bool = True,
        displacement_scale: float = 100.0,
        num_points: int = 20,
        show_supports: bool = True,
        show_support_labels: bool = True,
        support_size_fraction: float = 0.05,
        plot_bending_moment: Optional[str] = None,
        moment_scale: Optional[float] = None,
        moment_num_points: int = 41,
        color_members_by_peak_moment: bool = False,
        show_moment_colorbar: bool = True,
        diagram_line_width_pixels: int = 6,
        diagram_on_deformed_centerline: bool = False,
        moment_style: str = "tube",
        show_reactions: bool = True,
        reaction_scale_fraction: float = 0.03,
        show_reaction_labels: bool = True,
        show_node_values: bool = False,
        length_unit: Optional[str] = None,
        force_unit: Optional[str] = None,
        interactive_diagrams: bool = False,
        diagram_plane: str = "auto",
    ):
        """
        Visualize a load case or combination in 3D using PyVista.

        When ``interactive_diagrams=True`` the viewer shows checkboxes for
        every available result layer (Displacement, N, Vy, Vz, Mx, My, Mz)
        so you can toggle them on/off interactively.

        When ``interactive_diagrams=False`` (default) the original two-branch
        behaviour is preserved:
        * ``plot_bending_moment=None``  → deformed shape
        * ``plot_bending_moment="M_y"`` → single moment diagram

        Args:
            diagram_plane: Controls which plane diagrams are drawn in.
                ``"auto"`` (default) detects the thinnest global dimension
                and draws all diagrams in the dominant plane.
                ``"XY"``, ``"XZ"``, ``"YZ"`` force a specific plane.
                ``"local"`` uses the member's local coordinate system axes
                (correct for full 3-D structures but may look odd for
                planar frames).
            interactive_diagrams: If True, show all diagram layers with toggle
                checkboxes.  ``plot_bending_moment`` is ignored in this mode.
            show_node_values: If True, display displacement values at nodes.
        """
        if self.resultsbundle is None:
            raise ValueError("No analysis results available.")
        if loadcase is not None and loadcombination is not None:
            raise ValueError("Specify either loadcase or loadcombination, not both.")

        # ---------------------------
        # Select which results to use
        # ---------------------------
        if loadcase is not None:
            _viewing_loadcase = True
            keys = list(self.resultsbundle.loadcases.keys())
            if isinstance(loadcase, int):
                try:
                    key = keys[loadcase - 1]
                except IndexError:
                    raise IndexError(f"Loadcase index {loadcase} is out of range.")
            else:
                key = str(loadcase)
                if key not in self.resultsbundle.loadcases:
                    available_loadcases = [
                        f"'{v.name}'" if getattr(v, "name", None) else f"'{k}'"
                        for k, v in self.resultsbundle.loadcases.items()
                    ]
                    raise KeyError(
                        f"Loadcase '{key}' not found. "
                        f"Available loadcases: {', '.join(available_loadcases) or 'none'}"
                    )
            chosen = self.resultsbundle.loadcases[key]

        elif loadcombination is not None:
            _viewing_loadcase = False
            keys = list(self.resultsbundle.loadcombinations.keys())
            if isinstance(loadcombination, int):
                try:
                    key = keys[loadcombination - 1]
                except IndexError:
                    raise IndexError(f"Loadcombination index {loadcombination} is out of range.")
            else:
                key = str(loadcombination)
                if key not in self.resultsbundle.loadcombinations:
                    available_combinations = [
                        f"'{v.name}'" if getattr(v, "name", None) else f"'{k}'"
                        for k, v in self.resultsbundle.loadcombinations.items()
                    ]
                    raise KeyError(
                        f"Loadcombination '{key}' not found. "
                        f"Available loadcombinations: {', '.join(available_combinations) or 'none'}"
                    )
            chosen = self.resultsbundle.loadcombinations[key]

        else:
            _viewing_loadcase = True
            if len(self.resultsbundle.loadcases) == 1 and not self.resultsbundle.loadcombinations:
                key = next(iter(self.resultsbundle.loadcases.keys()))
                chosen = self.resultsbundle.loadcases[key]
            else:
                available_loadcases = [
                    f"'{v.name}'" if getattr(v, "name", None) else f"'{k}'"
                    for k, v in self.resultsbundle.loadcases.items()
                ]
                available_combinations = [
                    f"'{v.name}'" if getattr(v, "name", None) else f"'{k}'"
                    for k, v in self.resultsbundle.loadcombinations.items()
                ]
                raise ValueError(
                    "Multiple results available – specify loadcase= or loadcombination=. "
                    f"Available loadcases: {', '.join(available_loadcases) or 'none'}. "
                    f"Available loadcombinations: {', '.join(available_combinations) or 'none'}."
                )

        # ---------------------------
        # Plotter + global scales
        # ---------------------------
        import pyvista as pv

        plotter = pv.Plotter()
        plotter.add_axes()

        min_coordinates, max_coordinates = self.get_structure_bounds()
        if min_coordinates and max_coordinates:
            structure_size = np.linalg.norm(np.array(max_coordinates) - np.array(min_coordinates))
        else:
            structure_size = 1.0
        support_arrow_scale = max(1e-6, structure_size * support_size_fraction)

        # ---------------------------
        # Diagram plane detection
        # ---------------------------
        _plane_normal: Optional[np.ndarray] = None
        _plane_map = {
            "xy": np.array([0.0, 0.0, 1.0]),
            "xz": np.array([0.0, 1.0, 0.0]),
            "yz": np.array([1.0, 0.0, 0.0]),
        }
        dp_lower = diagram_plane.lower().strip()
        if dp_lower in _plane_map:
            _plane_normal = _plane_map[dp_lower]
        elif dp_lower == "auto":
            if min_coordinates and max_coordinates:
                spans = np.array(max_coordinates) - np.array(min_coordinates)
                thin_axis = int(np.argmin(spans))
                # If thinnest dimension is < 1 % of structure size → planar
                if spans[thin_axis] < 0.01 * structure_size:
                    normal = np.zeros(3)
                    normal[thin_axis] = 1.0
                    _plane_normal = normal
        # dp_lower == "local" or auto didn't detect a plane → _plane_normal stays None

        # ---------------------------
        # Unit labels
        # ---------------------------
        _us = self.settings.unit_settings if self.settings else None
        if length_unit is None:
            length_unit = getattr(_us, "length_unit", "m") if _us else "m"
        if force_unit is None:
            force_unit = getattr(_us, "force_unit", "N") if _us else "N"
        moment_unit = f"{force_unit}·{length_unit}"

        # ---------------------------
        # Helpers
        # ---------------------------
        def _normalize_key(s: str) -> str:
            return str(s).lower().replace("_", "")

        def _get_comp(obj, name: str):
            if obj is None:
                return None
            candidates = [
                name,
                name.replace("_", ""),
                name.lower(),
                name.upper(),
                name.capitalize(),
                name.replace("_", "").lower(),
            ]
            for candidate in candidates:
                if hasattr(obj, candidate):
                    return getattr(obj, candidate)
            if isinstance(obj, dict):
                for candidate in candidates:
                    if candidate in obj:
                        return obj[candidate]
                for key_iter, value_iter in obj.items():
                    if _normalize_key(key_iter) == _normalize_key(name):
                        return value_iter
            return None

        def _offset_axis(member: Member, component_name: str) -> np.ndarray:
            """Return the axis along which the diagram is offset.

            When a *plane normal* has been detected (or set via
            ``diagram_plane``), every diagram is drawn perpendicular to
            the member axis **within that plane**, which is the standard
            engineering convention for planar frames.

            When no plane is active (``diagram_plane="local"`` or a true
            3-D structure) the member's local coordinate system is used:
            - My → local z, Mz → local y, etc.
            """
            if _plane_normal is not None:
                # In-plane perpendicular: cross(member_axis, plane_normal)
                p0 = np.array([member.start_node.X, member.start_node.Y, member.start_node.Z], dtype=float)
                p1 = np.array([member.end_node.X, member.end_node.Y, member.end_node.Z], dtype=float)
                lx = p1 - p0
                length = float(np.linalg.norm(lx))
                if length > 1e-12:
                    lx /= length
                perp = np.cross(lx, _plane_normal)
                norm = float(np.linalg.norm(perp))
                if norm > 1e-12:
                    return perp / norm
                # Member is parallel to the plane normal (unlikely but
                # fall through to local axes)

            # Full 3-D fallback: use local coordinate system
            lx, ly, lz = member.local_coordinate_system()
            lower = component_name.lower().replace("_", "")
            if lower in ("my",):
                return np.asarray(lz, dtype=float)
            if lower in ("mz",):
                return np.asarray(ly, dtype=float)
            if lower in ("vy", "fy"):
                return np.asarray(ly, dtype=float)
            if lower in ("vz", "fz"):
                return np.asarray(lz, dtype=float)
            if lower in ("mx", "n", "fx"):
                return np.asarray(ly, dtype=float)
            return np.asarray(ly, dtype=float)  # fallback

        def _resample(num: int, s: np.ndarray, y: np.ndarray) -> np.ndarray:
            s_target = np.linspace(0.0, 1.0, num=num)
            return np.interp(s_target, s, y)

        def _fetch_member_line_curve(member_id: int, comp: str) -> Optional[Tuple[np.ndarray, np.ndarray]]:
            for attr_name in [
                "internal_forces_by_member",
                "member_internal_forces",
                "line_forces_by_member",
                "member_line_forces",
                "element_forces_by_member",
            ]:
                container = getattr(chosen, attr_name, None)
                if container and str(member_id) in container:
                    record = container[str(member_id)]
                    if isinstance(record, dict):
                        s_vals = _get_comp(record, "s")
                        m_vals = _get_comp(record, comp)
                        if s_vals is not None and m_vals is not None:
                            s_vals = np.asarray(s_vals, dtype=float)
                            m_vals = np.asarray(m_vals, dtype=float)
                            if s_vals.size > 1 and s_vals.size == m_vals.size:
                                return s_vals, m_vals

            members_map = getattr(chosen, "members", None)
            if members_map and str(member_id) in members_map:
                member_obj = members_map[str(member_id)]
                for nested_name in ["internal_forces", "line_forces"]:
                    nested = getattr(member_obj, nested_name, None)
                    if nested is not None:
                        s_vals = _get_comp(nested, "s")
                        m_vals = _get_comp(nested, comp)
                        if s_vals is not None and m_vals is not None:
                            s_vals = np.asarray(s_vals, dtype=float)
                            m_vals = np.asarray(m_vals, dtype=float)
                            if s_vals.size > 1 and s_vals.size == m_vals.size:
                                return s_vals, m_vals
            return None

        def _fetch_member_end_forces(member_id: int, comp: str) -> Optional[Tuple[np.ndarray, np.ndarray]]:
            container = getattr(chosen, "member_results", None)
            if container and str(member_id) in container:
                rec = container[str(member_id)]
                start_forces = (
                    getattr(rec, "start_node_forces", None)
                    or getattr(rec, "start", None)
                    or getattr(rec, "i", None)
                )
                end_forces = (
                    getattr(rec, "end_node_forces", None)
                    or getattr(rec, "end", None)
                    or getattr(rec, "j", None)
                )
                start_val = _get_comp(start_forces, comp)
                end_val = _get_comp(end_forces, comp)
                if start_val is not None and end_val is not None:
                    s_vals = np.array([0.0, 1.0], dtype=float)
                    m_vals = np.array([float(start_val), float(end_val)], dtype=float)
                    return s_vals, m_vals

            for attr_name in [
                "member_end_forces",
                "end_forces_by_member",
                "member_forces",
                "element_forces",
                "elements_end_forces",
            ]:
                cont = getattr(chosen, attr_name, None)
                if cont and str(member_id) in cont:
                    rec = cont[str(member_id)]
                    start = (
                        rec.get("start") or rec.get("i") or rec.get("node_i") or rec.get("end_i")
                        if isinstance(rec, dict)
                        else None
                    )
                    end = (
                        rec.get("end") or rec.get("j") or rec.get("node_j") or rec.get("end_j")
                        if isinstance(rec, dict)
                        else None
                    )
                    start_val = _get_comp(start, comp)
                    end_val = _get_comp(end, comp)
                    if start_val is None and isinstance(rec, dict):
                        for k, v in rec.items():
                            key_norm = _normalize_key(k)
                            pm_norm = _normalize_key(comp)
                            if key_norm.startswith(pm_norm) and key_norm.endswith("i"):
                                start_val = float(v)
                            if key_norm.startswith(pm_norm) and key_norm.endswith("j"):
                                end_val = float(v)
                    if start_val is not None and end_val is not None:
                        s_vals = np.array([0.0, 1.0], dtype=float)
                        m_vals = np.array([float(start_val), float(end_val)], dtype=float)
                        return s_vals, m_vals
            return None

        def _fallback_single_cantilever(member: Member, comp: str) -> Optional[Tuple[np.ndarray, np.ndarray]]:
            if len(self.get_all_members()) != 1:
                return None
            start_is_supported = getattr(member.start_node, "nodal_support", None) is not None
            end_is_supported = getattr(member.end_node, "nodal_support", None) is not None
            if not (start_is_supported ^ end_is_supported):
                return None
            reactions = getattr(chosen, "reaction_nodes", {}) or {}
            if not reactions:
                return None
            supported_node_id = member.start_node.id if start_is_supported else member.end_node.id
            rec = reactions.get(str(supported_node_id))
            if not rec or getattr(rec, "nodal_forces", None) is None:
                return None
            val = _get_comp(rec.nodal_forces, comp)
            if not isinstance(val, (int, float)):
                return None
            if start_is_supported:
                return np.array([0.0, 1.0], float), np.array([float(val), 0.0], float)
            else:
                return np.array([0.0, 1.0], float), np.array([0.0, float(val)], float)

        # ── Distributed-load enrichment helpers ──────────────────────
        def _get_member_distributed_loads(member_id: int):
            """Return [(DistributedLoad, factor), ...] for this member."""
            pairs = []
            if _viewing_loadcase:
                for lc in self.get_all_load_cases():
                    if lc.name == key or str(lc.id) == str(key):
                        for dl in lc.distributed_loads:
                            mid = dl.member.id if hasattr(dl.member, "id") else dl.member
                            if int(mid) == int(member_id):
                                pairs.append((dl, 1.0))
                        break
            else:
                for combo in self.load_combinations:
                    if combo.name == key or str(combo.id) == str(key):
                        for lc_obj, factor in combo.load_cases_factors.items():
                            for dl in lc_obj.distributed_loads:
                                mid = dl.member.id if hasattr(dl.member, "id") else dl.member
                                if int(mid) == int(member_id):
                                    pairs.append((dl, factor))
                        break
            return pairs

        def _get_all_start_end_forces(member_id: int):
            """Return (start_dict, end_dict) with all 6 force components, or None."""
            container = getattr(chosen, "member_results", None)
            if not container or str(member_id) not in container:
                return None
            rec = container[str(member_id)]
            sf = (
                getattr(rec, "start_node_forces", None)
                or getattr(rec, "start", None)
                or getattr(rec, "i", None)
            )
            ef = getattr(rec, "end_node_forces", None) or getattr(rec, "end", None) or getattr(rec, "j", None)
            if sf is None or ef is None:
                return None
            start = {}
            end = {}
            for c in ("fx", "fy", "fz", "mx", "my", "mz"):
                sv = _get_comp(sf, c)
                ev = _get_comp(ef, c)
                if sv is None or ev is None:
                    return None
                start[c] = float(sv)
                end[c] = float(ev)
            return start, end

        def _enrich_with_loads(
            member, comp: str, s_raw: np.ndarray, m_raw: np.ndarray, n_pts: int
        ) -> Optional[Tuple[np.ndarray, np.ndarray]]:
            """Reconstruct internal-force curve using section-cut equilibrium.

            If the member has distributed loads, the linear interpolation
            between the two end values is replaced by the analytically
            correct curve (parabolic for uniform loads, cubic for
            triangular, etc.).  Returns ``None`` when no enrichment is
            needed (no distributed loads, or data unavailable).
            """
            if len(s_raw) != 2:
                return None  # already has intermediate data
            dl_pairs = _get_member_distributed_loads(member.id)
            if not dl_pairs:
                return None  # no distributed loads → linear is correct
            forces = _get_all_start_end_forces(member.id)
            if forces is None:
                return None
            sf, _ = forces

            # Member geometry (global)
            d = np.array(
                [
                    member.end_node.X - member.start_node.X,
                    member.end_node.Y - member.start_node.Y,
                    member.end_node.Z - member.start_node.Z,
                ],
                dtype=float,
            )
            L = float(np.linalg.norm(d))
            if L < 1e-12:
                return None

            s_arr = np.linspace(0.0, 1.0, n_pts)
            values = np.zeros(n_pts, dtype=float)
            comp_lower = comp.lower().replace("_", "")

            # Map component to the equilibrium formula
            # Forces:  f_comp(s) = f_start + sum_loads integral
            # Moments: m_comp(s) = m_start + s*K_f + sum_loads C*integral
            is_force = comp_lower in ("fx", "fy", "fz", "n")
            is_moment = comp_lower in ("mx", "my", "mz")

            # Determine the global axis index for force components
            _force_axis = {"fx": 0, "n": 0, "fy": 1, "fz": 2}
            # Determine moment cross-coupling coefficients
            # Mz = r_x*Fy - r_y*Fx, where r = -s*d
            _moment_coeff = {
                "mz": {
                    "k_force": d[1] * sf["fx"] - d[0] * sf["fy"],
                    "cross": lambda dl_dir: d[0] * dl_dir[1] - d[1] * dl_dir[0],
                },
                "my": {
                    "k_force": d[2] * sf["fx"] - d[0] * sf["fz"],
                    "cross": lambda dl_dir: d[0] * dl_dir[2] - d[2] * dl_dir[0],
                },
                "mx": {
                    "k_force": d[2] * sf["fy"] - d[1] * sf["fz"],
                    "cross": lambda dl_dir: d[1] * dl_dir[2] - d[2] * dl_dir[1],
                },
            }

            if is_force:
                ax = _force_axis.get(comp_lower)
                if ax is None:
                    return None
                f_start = sf[comp_lower] if comp_lower != "n" else sf["fx"]
                for i, s in enumerate(s_arr):
                    val = f_start
                    for dl, factor in dl_pairs:
                        val += factor * _dl_force_integral(dl, L, s, ax)
                    values[i] = val
            elif is_moment:
                mc = _moment_coeff.get(comp_lower)
                if mc is None:
                    return None
                m_start = sf[comp_lower]
                k_f = mc["k_force"]
                for i, s in enumerate(s_arr):
                    val = m_start + s * k_f
                    for dl, factor in dl_pairs:
                        C = mc["cross"](dl.direction)
                        val += factor * C * _dl_moment_integral(dl, L, s)
                    values[i] = val
            else:
                return None  # unknown component

            return s_arr, values

        def _dl_force_integral(dl, L: float, s: float, axis: int) -> float:
            """∫₀^min(b,s) w(t)·dir[axis]·L dt  (force accumulation)."""
            a, b = dl.start_frac, dl.end_frac
            u = min(b, s)
            if u <= a:
                return 0.0
            span = b - a
            if span < 1e-14:
                return 0.0
            w1, w2 = dl.magnitude, dl.end_magnitude
            du = u - a
            integral = w1 * du + (w2 - w1) / span * du**2 / 2.0
            return dl.direction[axis] * L * integral

        def _dl_moment_integral(dl, L: float, s: float) -> float:
            """∫_a^min(b,s) (t − s)·w(t)·L dt  (moment contribution)."""
            a, b = dl.start_frac, dl.end_frac
            u = min(b, s)
            if u <= a:
                return 0.0
            span = b - a
            if span < 1e-14:
                return 0.0
            w1, w2 = dl.magnitude, dl.end_magnitude
            du = u - a
            d2 = u**2 - a**2
            d3 = u**3 - a**3
            alpha = (w2 - w1) / span
            term1 = w1 * (d2 / 2.0 - s * du)
            term2 = alpha * (d3 / 3.0 - (a + s) * d2 / 2.0 + a * s * du)
            return L * (term1 + term2)

        def _plot_reactions():
            if not show_reactions:
                return

            reaction_nodes = getattr(chosen, "reaction_nodes", {}) or {}
            if not reaction_nodes:
                return

            diag_length = float(structure_size) if structure_size > 0.0 else 1.0
            base_arrow_length = max(1e-6, diag_length * float(reaction_scale_fraction))
            min_len = 0.1 * base_arrow_length
            max_len = 1.5 * base_arrow_length

            max_force_magnitude = 0.0
            for node_id_string, reaction in reaction_nodes.items():
                forces = reaction.nodal_forces
                fv = np.array([forces.fx, forces.fy, forces.fz], dtype=float)
                mag = float(np.linalg.norm(fv))
                if mag > max_force_magnitude:
                    max_force_magnitude = mag

            if max_force_magnitude <= 0.0:
                return

            added_legend = False
            for node_id_string, reaction in reaction_nodes.items():
                forces = reaction.nodal_forces
                fv = np.array([forces.fx, forces.fy, forces.fz], dtype=float)
                mag = float(np.linalg.norm(fv))
                if mag <= 0.0:
                    continue

                try:
                    node_obj = self.get_node_by_pk(int(node_id_string))
                except Exception:
                    node_obj = None

                if node_obj is not None:
                    pos = np.array([node_obj.X, node_obj.Y, node_obj.Z], dtype=float)
                else:
                    loc = reaction.location
                    pos = np.array([loc.X, loc.Y, loc.Z], dtype=float)

                direction = fv / mag
                arrow_length = np.clip(base_arrow_length * (mag / max_force_magnitude), min_len, max_len)
                arrow_vec = direction * arrow_length

                plotter.add_arrows(
                    pos,
                    arrow_vec,
                    color="magenta",
                    label="Reaction forces" if not added_legend else None,
                )
                if show_reaction_labels:
                    label_text = (
                        f"Rx={forces.fx:.2f} {force_unit}, "
                        f"Ry={forces.fy:.2f} {force_unit}, "
                        f"Rz={forces.fz:.2f} {force_unit}"
                    )
                    plotter.add_point_labels(
                        pos + arrow_vec * 0.6,
                        [label_text],
                        font_size=16,
                        text_color="magenta",
                        always_visible=True,
                    )
                added_legend = True

        # ---------------------------
        # Compute displacements (always – needed for deformed centerlines)
        # ---------------------------
        node_displacements: dict[int, Tuple[np.ndarray, np.ndarray]] = {}
        displacement_nodes = getattr(chosen, "displacement_nodes", {})
        for node_id_string, disp in displacement_nodes.items():
            node_id = int(node_id_string)
            node = self.get_node_by_pk(node_id)
            if node is None:
                continue
            if disp:
                d_global = np.array([disp.dx, disp.dy, disp.dz], dtype=float)
                r_global = np.array([disp.rx, disp.ry, disp.rz], dtype=float)
            else:
                d_global = np.zeros(3, dtype=float)
                r_global = np.zeros(3, dtype=float)
            node_displacements[node_id] = (d_global, r_global)

        # ================================================================
        # NON-INTERACTIVE MODE  (original behaviour, backward compatible)
        # ================================================================
        if not interactive_diagrams:
            if plot_bending_moment is None:
                # ── BRANCH A: Displacement only ──
                centerline_samples = num_points
                extrusion_samples = max(num_points * 2, 2 * num_points + 1)

                labeled_lines = False
                labeled_def_section = False
                labeled_org_section = False

                for member in self.get_all_members():
                    d0_gl, r0_gl = node_displacements.get(member.start_node.id, (np.zeros(3), np.zeros(3)))
                    d1_gl, r1_gl = node_displacements.get(member.end_node.id, (np.zeros(3), np.zeros(3)))

                    original_curve, deformed_curve = centerline_path_points(
                        member,
                        d0_gl,
                        r0_gl,
                        d1_gl,
                        r1_gl,
                        centerline_samples,
                        displacement_scale,
                    )
                    deformed_path_points = np.ascontiguousarray(
                        pv.Spline(deformed_curve, extrusion_samples).points,
                        dtype=float,
                    )
                    deformed_path_points[0] = deformed_curve[0]
                    deformed_path_points[-1] = deformed_curve[-1]

                    plotter.add_mesh(
                        pv.lines_from_points(original_curve),
                        color="blue",
                        line_width=2,
                        label=None if labeled_lines else "Original Shape",
                    )
                    plotter.add_mesh(
                        pv.lines_from_points(deformed_path_points),
                        color="red",
                        line_width=2,
                        label=None if labeled_lines else "Deformed Shape",
                    )
                    labeled_lines = True

                    if show_sections:
                        section = getattr(member, "section", None)
                        if section is not None and getattr(section, "shape_path", None) is not None:
                            if displacement:
                                deformed_mesh = extrude_along_path(section.shape_path, deformed_path_points)
                                plotter.add_mesh(
                                    deformed_mesh,
                                    color="red",
                                    label=None if labeled_def_section else "Deformed Section",
                                )
                                labeled_def_section = True

                            s_node = member.start_node
                            e_node = member.end_node
                            coords_2d, edges = section.shape_path.get_shape_geometry()
                            coords_local = np.array([[0.0, y, z] for y, z in coords_2d], dtype=np.float32)
                            rotation_matrix = np.column_stack(member.local_coordinate_system())
                            origin = np.array([s_node.X, s_node.Y, s_node.Z], dtype=float)
                            coords_global = (coords_local @ rotation_matrix.T + origin).astype(np.float32)

                            polydata = pv.PolyData(coords_global)
                            line_array = []
                            for a_index, b_index in edges:
                                line_array.extend((2, a_index, b_index))
                            polydata.lines = np.array(line_array, dtype=np.int32)

                            direction = np.array([e_node.X, e_node.Y, e_node.Z], dtype=float) - origin
                            original_mesh = polydata.extrude(direction, capping=True)
                            plotter.add_mesh(
                                original_mesh,
                                color="steelblue",
                                label=None if labeled_org_section else "Original Section",
                            )
                            labeled_org_section = True

                if show_nodes:
                    originals = []
                    deformed_pts = []
                    for node in self.get_all_nodes():
                        o = np.array([node.X, node.Y, node.Z], dtype=float)
                        dgl, _ = node_displacements.get(node.id, (np.zeros(3), np.zeros(3)))
                        originals.append(o)
                        deformed_pts.append(o + dgl * displacement_scale)
                    originals = np.array(originals, dtype=float)
                    deformed_pts = np.array(deformed_pts, dtype=float)
                    plotter.add_mesh(
                        pv.PolyData(originals).glyph(scale=False, geom=pv.Sphere(radius=0.05)),
                        color="blue",
                        label="Original Nodes",
                    )
                    plotter.add_mesh(
                        pv.PolyData(deformed_pts).glyph(scale=False, geom=pv.Sphere(radius=0.05)),
                        color="red",
                        label="Deformed Nodes",
                    )

                    if show_node_values:
                        displacement_nodes_map = getattr(chosen, "displacement_nodes", {}) or {}
                        for node in self.get_all_nodes():
                            disp = displacement_nodes_map.get(str(node.id))
                            if disp is None:
                                continue
                            dgl, _ = node_displacements.get(node.id, (np.zeros(3), np.zeros(3)))
                            label_pos = (
                                np.array([node.X, node.Y, node.Z], dtype=float) + dgl * displacement_scale
                            )
                            label_text = (
                                f"N{node.id}\n"
                                f"dx={disp.dx:.2f} {length_unit}\n"
                                f"dy={disp.dy:.2f} {length_unit}\n"
                                f"dz={disp.dz:.2f} {length_unit}"
                            )
                            plotter.add_point_labels(
                                label_pos,
                                [label_text],
                                font_size=10,
                                text_color="darkred",
                                always_visible=True,
                            )

                if show_supports:
                    legend_added_for_type: set[str] = set()
                    axis_unit_vectors = {
                        "X": np.array([1.0, 0.0, 0.0]),
                        "Y": np.array([0.0, 1.0, 0.0]),
                        "Z": np.array([0.0, 0.0, 1.0]),
                    }
                    for node in self.get_all_nodes():
                        nodal_support = getattr(node, "nodal_support", None)
                        if not nodal_support:
                            continue
                        node_position = np.array([node.X, node.Y, node.Z], dtype=float)
                        for axis_name, axis_vector in axis_unit_vectors.items():
                            condition_type = get_condition_type(
                                nodal_support.displacement_conditions.get(axis_name)
                            )
                            color_value = color_for_condition_type(condition_type)
                            label = None
                            if condition_type not in legend_added_for_type:
                                label = f"Support {axis_name} – {condition_type.title()}"
                                legend_added_for_type.add(condition_type)
                            plotter.add_arrows(
                                node_position,
                                axis_vector * support_arrow_scale,
                                color=color_value,
                                label=label,
                            )
                        if show_support_labels:
                            label_text = format_support_label(nodal_support)
                            label_position = node_position + np.array([1, 1, 1], dtype=float) * (
                                support_arrow_scale * 0.6
                            )
                            plotter.add_point_labels(
                                label_position,
                                [label_text],
                                font_size=12,
                                text_color="black",
                                always_visible=True,
                            )

                _plot_reactions()
                plotter.add_legend()
                plotter.show_grid(
                    color="gray",
                    xtitle=f"X [{length_unit}]",
                    ytitle=f"Y [{length_unit}]",
                    ztitle=f"Z [{length_unit}]",
                )
                plotter.view_isometric()
                plotter.show(
                    title=f'3D Results: "{chosen.name}"  (displacement scale: {displacement_scale}×)'
                )
                return

            # ── BRANCH B: Single moment diagram (backward compatible) ──
            diagram_polys: list[pv.PolyData] = []
            diagram_vals: list[np.ndarray] = []
            offset_axes_list: list[np.ndarray] = []
            peak_abs_by_member: dict[int, float] = {}

            for member in self.get_all_members():
                curve = _fetch_member_line_curve(member.id, plot_bending_moment)
                if curve is None:
                    curve = _fetch_member_end_forces(member.id, plot_bending_moment)
                if curve is None:
                    curve = _fallback_single_cantilever(member, plot_bending_moment)
                if curve is None:
                    continue

                s_raw, m_raw = curve
                enriched = _enrich_with_loads(
                    member,
                    plot_bending_moment,
                    np.asarray(s_raw, float),
                    np.asarray(m_raw, float),
                    moment_num_points,
                )
                if enriched is not None:
                    s_raw, m_raw = enriched
                m_resampled = _resample(moment_num_points, np.asarray(s_raw, float), np.asarray(m_raw, float))

                if diagram_on_deformed_centerline:
                    d0_gl, r0_gl = node_displacements.get(member.start_node.id, (np.zeros(3), np.zeros(3)))
                    d1_gl, r1_gl = node_displacements.get(member.end_node.id, (np.zeros(3), np.zeros(3)))
                    _, def_curve = centerline_path_points(
                        member,
                        d0_gl,
                        r0_gl,
                        d1_gl,
                        r1_gl,
                        moment_num_points,
                        displacement_scale,
                    )
                    path_points = np.ascontiguousarray(
                        pv.Spline(def_curve, moment_num_points).points,
                        dtype=float,
                    )
                    path_points[0] = def_curve[0]
                    path_points[-1] = def_curve[-1]
                else:
                    p0 = np.array(
                        [member.start_node.X, member.start_node.Y, member.start_node.Z], dtype=float
                    )
                    p1 = np.array([member.end_node.X, member.end_node.Y, member.end_node.Z], dtype=float)
                    t = np.linspace(0.0, 1.0, moment_num_points)[:, None]
                    path_points = p0[None, :] * (1.0 - t) + p1[None, :] * t

                axis = _offset_axis(member, plot_bending_moment)

                poly = pv.PolyData(path_points.copy())
                poly.lines = np.hstack(
                    [
                        np.array([moment_num_points], dtype=np.int32),
                        np.arange(moment_num_points, dtype=np.int32),
                    ]
                )
                diagram_polys.append(poly)
                diagram_vals.append(m_resampled)
                offset_axes_list.append(axis)
                peak_abs_by_member[member.id] = float(np.max(np.abs(m_resampled)))

            if not diagram_polys:
                pts = []
                lines = []
                idx = 0
                for m in self.get_all_members():
                    s = m.start_node
                    e = m.end_node
                    pts.extend([(s.X, s.Y, s.Z), (e.X, e.Y, e.Z)])
                    lines.extend([2, idx, idx + 1])
                    idx += 2
                if pts:
                    pts = np.array(pts, dtype=np.float32)
                    poly = pv.PolyData(pts)
                    poly.lines = np.array(lines, dtype=np.int32)
                    plotter.add_mesh(poly, color="gray", line_width=2.0, label="Members")
            else:
                global_abs_max = float(np.max([np.max(np.abs(v)) for v in diagram_vals])) or 1.0
                effective_moment_scale = (
                    moment_scale
                    if (moment_scale is not None and moment_scale > 0.0)
                    else (0.06 * structure_size / global_abs_max)
                )
                if moment_style.lower() == "tube":
                    for polydata, values, off_axis in zip(diagram_polys, diagram_vals, offset_axes_list):
                        centerline_pts = polydata.points.copy()
                        diagram_pts = (
                            centerline_pts + (effective_moment_scale * values[:, None]) * off_axis[None, :]
                        )
                        n = len(centerline_pts)
                        ribbon_pts = np.vstack([centerline_pts, diagram_pts])
                        faces = []
                        for i in range(n - 1):
                            faces.extend([3, i, i + 1, n + i])
                            faces.extend([3, i + 1, n + i + 1, n + i])
                        ribbon = pv.PolyData(ribbon_pts, np.array(faces, dtype=np.int32))
                        ribbon.point_data["moment"] = np.concatenate([values, values]).astype(float)
                        plotter.add_mesh(
                            ribbon, scalars="moment", opacity=0.35, show_edges=False, show_scalar_bar=False
                        )
                        # Outline
                        outline_pts = np.vstack([centerline_pts[0:1], diagram_pts, centerline_pts[-1:]])
                        n_out = len(outline_pts)
                        outline_line = np.hstack(
                            [
                                np.array([n_out], dtype=np.int32),
                                np.arange(n_out, dtype=np.int32),
                            ]
                        )
                        outline_poly = pv.PolyData(outline_pts)
                        outline_poly.lines = outline_line
                        outline_poly.point_data["moment"] = np.concatenate(
                            [values[0:1], values, values[-1:]]
                        ).astype(float)
                        plotter.add_mesh(
                            outline_poly, scalars="moment", line_width=2.5, show_scalar_bar=False
                        )
                elif moment_style.lower() == "line":
                    for polydata, values in zip(diagram_polys, diagram_vals):
                        polydata["moment"] = values.astype(float)
                        plotter.add_mesh(
                            polydata,
                            scalars="moment",
                            line_width=diagram_line_width_pixels,
                            show_scalar_bar=False,
                        )
                else:
                    raise ValueError("moment_style must be 'tube' or 'line'")
                if show_moment_colorbar:
                    plotter.add_scalar_bar(title=f"{plot_bending_moment} [{moment_unit}]")

                # Member centerlines
                all_points = []
                all_lines = []
                member_scalar_values = []
                point_offset = 0
                for member in self.get_all_members():
                    s = member.start_node
                    e = member.end_node
                    all_points.append((s.X, s.Y, s.Z))
                    all_points.append((e.X, e.Y, e.Z))
                    all_lines.extend([2, point_offset, point_offset + 1])
                    point_offset += 2
                    if color_members_by_peak_moment:
                        member_scalar_values.extend([peak_abs_by_member.get(member.id, 0.0)] * 2)
                if all_points:
                    all_points = np.array(all_points, dtype=np.float32)
                    lines_poly = pv.PolyData(all_points)
                    lines_poly.lines = np.array(all_lines, dtype=np.int32)
                    if color_members_by_peak_moment and member_scalar_values:
                        lines_poly["peak_abs_moment"] = np.array(member_scalar_values, dtype=float)
                        plotter.add_mesh(lines_poly, scalars="peak_abs_moment", line_width=3.0)
                        if show_moment_colorbar:
                            plotter.add_scalar_bar(
                                title=f"Peak |{plot_bending_moment}| [{moment_unit}] per member"
                            )
                    else:
                        plotter.add_mesh(lines_poly, color="blue", line_width=2.0, label="Members")

            if show_nodes:
                node_positions = np.array([(n.X, n.Y, n.Z) for n in self.get_all_nodes()], dtype=np.float32)
                cloud = pv.PolyData(node_positions)
                glyph = cloud.glyph(
                    geom=pv.Sphere(radius=max(1e-6, structure_size * 0.01)), scale=False, orient=False
                )
                plotter.add_mesh(glyph, color="black", label="Nodes")

            if show_supports:
                legend_added_for_type: set[str] = set()
                axis_unit_vectors = {
                    "X": np.array([1.0, 0.0, 0.0]),
                    "Y": np.array([0.0, 1.0, 0.0]),
                    "Z": np.array([0.0, 0.0, 1.0]),
                }
                for node in self.get_all_nodes():
                    nodal_support = getattr(node, "nodal_support", None)
                    if not nodal_support:
                        continue
                    node_position = np.array([node.X, node.Y, node.Z], dtype=float)
                    for axis_name, axis_vector in axis_unit_vectors.items():
                        condition_type = get_condition_type(
                            nodal_support.displacement_conditions.get(axis_name)
                        )
                        color_value = color_for_condition_type(condition_type)
                        label = None
                        if condition_type not in legend_added_for_type:
                            label = f"Support {axis_name} – {condition_type.title()}"
                            legend_added_for_type.add(condition_type)
                        plotter.add_arrows(
                            node_position,
                            axis_vector * support_arrow_scale,
                            color=color_value,
                            label=label,
                        )
                    if show_support_labels:
                        text = format_support_label(nodal_support)
                        label_pos = node_position + np.array([1, 1, 1], dtype=float) * (
                            support_arrow_scale * 0.6
                        )
                        plotter.add_point_labels(
                            label_pos,
                            [text],
                            font_size=12,
                            text_color="black",
                            always_visible=True,
                        )

            _plot_reactions()
            plotter.add_legend()
            plotter.show_grid(
                color="gray",
                xtitle=f"X [{length_unit}]",
                ytitle=f"Y [{length_unit}]",
                ztitle=f"Z [{length_unit}]",
            )
            plotter.view_isometric()
            plotter.show(title=f'Bending Moment Diagram: {plot_bending_moment} – "{chosen.name}"')
            return

        # ================================================================
        # INTERACTIVE MODE  (interactive_diagrams=True)
        # ================================================================

        # ── Build member centerlines (always visible as base) ────────
        all_pts = []
        all_lines = []
        pt_off = 0
        for member in self.get_all_members():
            s = member.start_node
            e = member.end_node
            all_pts.append((s.X, s.Y, s.Z))
            all_pts.append((e.X, e.Y, e.Z))
            all_lines.extend([2, pt_off, pt_off + 1])
            pt_off += 2
        if all_pts:
            all_pts_arr = np.array(all_pts, dtype=np.float32)
            base_poly = pv.PolyData(all_pts_arr)
            base_poly.lines = np.array(all_lines, dtype=np.int32)
            plotter.add_mesh(base_poly, color="steelblue", line_width=2.0, label="Members")

        if show_nodes:
            node_positions = np.array([(n.X, n.Y, n.Z) for n in self.get_all_nodes()], dtype=np.float32)
            cloud = pv.PolyData(node_positions)
            glyph = cloud.glyph(
                geom=pv.Sphere(radius=max(1e-6, structure_size * 0.01)),
                scale=False,
                orient=False,
            )
            _node_actor = plotter.add_mesh(glyph, color="black", label="Nodes")
        else:
            _node_actor = None

        if show_supports:
            legend_added_for_type: set[str] = set()
            axis_unit_vectors = {
                "X": np.array([1.0, 0.0, 0.0]),
                "Y": np.array([0.0, 1.0, 0.0]),
                "Z": np.array([0.0, 0.0, 1.0]),
            }
            for node in self.get_all_nodes():
                nodal_support = getattr(node, "nodal_support", None)
                if not nodal_support:
                    continue
                node_position = np.array([node.X, node.Y, node.Z], dtype=float)
                for axis_name, axis_vector in axis_unit_vectors.items():
                    condition_type = get_condition_type(nodal_support.displacement_conditions.get(axis_name))
                    color_value = color_for_condition_type(condition_type)
                    label = None
                    if condition_type not in legend_added_for_type:
                        label = f"Support {axis_name} – {condition_type.title()}"
                        legend_added_for_type.add(condition_type)
                    plotter.add_arrows(
                        node_position,
                        axis_vector * support_arrow_scale,
                        color=color_value,
                        label=label,
                    )
                if show_support_labels:
                    text = format_support_label(nodal_support)
                    label_pos = node_position + np.array([1, 1, 1], dtype=float) * (support_arrow_scale * 0.6)
                    plotter.add_point_labels(
                        label_pos,
                        [text],
                        font_size=12,
                        text_color="black",
                        always_visible=True,
                    )

        _plot_reactions()

        # ── Helper: build displacement actors ────────────────────────
        def _build_displacement_actors():
            actors = []
            centerline_samples = num_points
            extrusion_samples = max(num_points * 2, 2 * num_points + 1)

            for member in self.get_all_members():
                d0_gl, r0_gl = node_displacements.get(member.start_node.id, (np.zeros(3), np.zeros(3)))
                d1_gl, r1_gl = node_displacements.get(member.end_node.id, (np.zeros(3), np.zeros(3)))
                _, deformed_curve = centerline_path_points(
                    member,
                    d0_gl,
                    r0_gl,
                    d1_gl,
                    r1_gl,
                    centerline_samples,
                    displacement_scale,
                )
                deformed_path = np.ascontiguousarray(
                    pv.Spline(deformed_curve, extrusion_samples).points,
                    dtype=float,
                )
                deformed_path[0] = deformed_curve[0]
                deformed_path[-1] = deformed_curve[-1]
                a = plotter.add_mesh(pv.lines_from_points(deformed_path), color="red", line_width=2)
                actors.append(a)

                if show_sections:
                    section = getattr(member, "section", None)
                    if section is not None and getattr(section, "shape_path", None) is not None:
                        deformed_mesh = extrude_along_path(section.shape_path, deformed_path)
                        a = plotter.add_mesh(deformed_mesh, color="red", opacity=0.4)
                        actors.append(a)

            # Deformed node spheres
            for node in self.get_all_nodes():
                dgl, _ = node_displacements.get(node.id, (np.zeros(3), np.zeros(3)))
                dp = np.array([node.X, node.Y, node.Z], dtype=float) + dgl * displacement_scale
                sphere = pv.Sphere(
                    radius=max(1e-6, structure_size * 0.008),
                    center=dp,
                )
                a = plotter.add_mesh(sphere, color="red")
                actors.append(a)

            return actors

        # ── Helper: build node displacement value label actors ────────
        def _build_node_value_actors():
            """Build displacement-value text label actors for each node."""
            value_actors = []
            displacement_nodes_map = getattr(chosen, "displacement_nodes", {}) or {}
            for node in self.get_all_nodes():
                disp = displacement_nodes_map.get(str(node.id))
                if disp is None:
                    continue
                dgl, _ = node_displacements.get(node.id, (np.zeros(3), np.zeros(3)))
                lp = np.array([node.X, node.Y, node.Z], dtype=float) + dgl * displacement_scale
                txt = (
                    f"N{node.id}\n"
                    f"dx={disp.dx:.2f} {length_unit}\n"
                    f"dy={disp.dy:.2f} {length_unit}\n"
                    f"dz={disp.dz:.2f} {length_unit}"
                )
                a = plotter.add_point_labels(
                    lp,
                    [txt],
                    font_size=10,
                    text_color="darkred",
                    always_visible=True,
                )
                value_actors.append(a)
            return value_actors

        # ── Helper: build diagram actors for one component ───────────
        def _build_diagram_actors(comp: str, color: str):
            """Build filled-ribbon diagram actors for a single internal-force component."""
            actors = []
            polys = []
            vals_list = []
            off_axes = []

            for member in self.get_all_members():
                curve = _fetch_member_line_curve(member.id, comp)
                if curve is None:
                    curve = _fetch_member_end_forces(member.id, comp)
                if curve is None:
                    curve = _fallback_single_cantilever(member, comp)
                if curve is None:
                    continue

                s_raw, m_raw = curve
                enriched = _enrich_with_loads(
                    member,
                    comp,
                    np.asarray(s_raw, float),
                    np.asarray(m_raw, float),
                    moment_num_points,
                )
                if enriched is not None:
                    s_raw, m_raw = enriched
                m_resampled = _resample(moment_num_points, np.asarray(s_raw, float), np.asarray(m_raw, float))

                if diagram_on_deformed_centerline:
                    d0, r0 = node_displacements.get(member.start_node.id, (np.zeros(3), np.zeros(3)))
                    d1, r1 = node_displacements.get(member.end_node.id, (np.zeros(3), np.zeros(3)))
                    _, dc = centerline_path_points(
                        member,
                        d0,
                        r0,
                        d1,
                        r1,
                        moment_num_points,
                        displacement_scale,
                    )
                    pp = np.ascontiguousarray(pv.Spline(dc, moment_num_points).points, dtype=float)
                    pp[0] = dc[0]
                    pp[-1] = dc[-1]
                else:
                    p0 = np.array(
                        [member.start_node.X, member.start_node.Y, member.start_node.Z], dtype=float
                    )
                    p1 = np.array([member.end_node.X, member.end_node.Y, member.end_node.Z], dtype=float)
                    t = np.linspace(0.0, 1.0, moment_num_points)[:, None]
                    pp = p0[None, :] * (1.0 - t) + p1[None, :] * t

                axis = _offset_axis(member, comp)
                poly = pv.PolyData(pp.copy())
                poly.lines = np.hstack(
                    [
                        np.array([moment_num_points], dtype=np.int32),
                        np.arange(moment_num_points, dtype=np.int32),
                    ]
                )
                polys.append(poly)
                vals_list.append(m_resampled)
                off_axes.append(axis)

            if not polys:
                return actors

            global_max = float(np.max([np.max(np.abs(v)) for v in vals_list])) or 1.0
            eff_scale = (
                moment_scale
                if (moment_scale is not None and moment_scale > 0.0)
                else (0.06 * structure_size / global_max)
            )

            for poly, values, off_ax in zip(polys, vals_list, off_axes):
                centerline_pts = poly.points.copy()
                diagram_pts = centerline_pts + (eff_scale * values[:, None]) * off_ax[None, :]

                # Build a filled ribbon surface between centerline and diagram
                n = len(centerline_pts)
                ribbon_pts = np.vstack([centerline_pts, diagram_pts])  # 2n points
                faces = []
                for i in range(n - 1):
                    # Two triangles per quad: (cl_i, cl_i+1, diag_i) and (cl_i+1, diag_i+1, diag_i)
                    faces.extend([3, i, i + 1, n + i])
                    faces.extend([3, i + 1, n + i + 1, n + i])
                ribbon = pv.PolyData(ribbon_pts, np.array(faces, dtype=np.int32))
                a_fill = plotter.add_mesh(ribbon, color=color, opacity=0.35, show_edges=False)
                actors.append(a_fill)

                # Outline: diagram curve + closing lines at start/end
                outline_pts = np.vstack(
                    [
                        centerline_pts[0:1],  # start on centerline
                        diagram_pts,  # diagram curve
                        centerline_pts[-1:],  # end on centerline
                    ]
                )
                n_out = len(outline_pts)
                outline_line = np.hstack(
                    [
                        np.array([n_out], dtype=np.int32),
                        np.arange(n_out, dtype=np.int32),
                    ]
                )
                outline_poly = pv.PolyData(outline_pts)
                outline_poly.lines = outline_line
                a_line = plotter.add_mesh(outline_poly, color=color, line_width=2.5, opacity=0.9)
                actors.append(a_line)

            return actors

        # ── Build all toggle-able layers ─────────────────────────────
        # Each entry: (label, color, actors, initially_visible)
        _layers: list[tuple[str, str, list, bool]] = []

        # Displacement layer
        disp_actors = _build_displacement_actors()
        _layers.append(("Displacement", "#FF0000", disp_actors, True))

        # Internal-force diagram layers
        _diagram_defs = [
            ("N (Axial)", "fx", "#E65100"),
            ("Vy (Shear)", "fy", "#1B5E20"),
            ("Vz (Shear)", "fz", "#0D47A1"),
            ("Mx (Torsion)", "mx", "#FF6F00"),
            ("My (Moment)", "my", "#4A148C"),
            ("Mz (Moment)", "mz", "#006064"),
        ]

        for label, comp, color in _diagram_defs:
            acts = _build_diagram_actors(comp, color)
            if acts:
                # Start with diagrams hidden; displacement visible
                for a in acts:
                    if hasattr(a, "SetVisibility"):
                        a.SetVisibility(False)
                _layers.append((label, color, acts, False))

        # Node value label actors (built always; visibility set below)
        _node_value_actors = _build_node_value_actors()
        for a in _node_value_actors:
            if hasattr(a, "SetVisibility"):
                a.SetVisibility(show_node_values)

        # ── Top-left: diagram-layer checkbox widgets ──────────────────
        _win_w, _win_h = plotter.window_size

        def _make_layer_toggle(actor_list):
            def toggle(flag):
                for a in actor_list:
                    if hasattr(a, "SetVisibility"):
                        a.SetVisibility(flag)
                plotter.render()

            return toggle

        for cb_idx, (label, color, actors, visible) in enumerate(_layers):
            _y = _win_h - 40 - cb_idx * 40
            plotter.add_checkbox_button_widget(
                _make_layer_toggle(actors),
                value=visible,
                position=(10, _y),
                size=30,
                color_on=color,
                color_off="grey",
            )
            plotter.add_text(
                label,
                position=(50, _y + 4),
                font_size=9,
                color=color,
            )

        # ── Top-right: node values / node visibility / member results toggles ──
        # "Member Results" toggles only the first layer (Displacement); the
        # individual diagram-layer checkboxes on the left control the rest.
        _first_layer_actors = _layers[0][2] if _layers else []

        _right_toggles = [
            ("Node Values", "darkred", _node_value_actors, show_node_values),
            ("Nodes", "black", [_node_actor] if _node_actor else [], show_nodes),
            ("Member Results", "#FF0000", _first_layer_actors, True),
        ]

        def _make_right_toggle(actor_list):
            def toggle(flag):
                for a in actor_list:
                    if hasattr(a, "SetVisibility"):
                        a.SetVisibility(flag)
                plotter.render()

            return toggle

        for btn_idx, (label, color, actors, initial) in enumerate(_right_toggles):
            _y = _win_h - 40 - btn_idx * 40
            _x_cb = _win_w - 200
            plotter.add_checkbox_button_widget(
                _make_right_toggle(actors),
                value=initial,
                position=(_x_cb, _y),
                size=30,
                color_on=color,
                color_off="grey",
            )
            plotter.add_text(
                label,
                position=(_x_cb + 40, _y + 4),
                font_size=9,
                color=color,
            )

        plotter.add_legend(loc="lower right")
        plotter.show_grid(
            color="gray",
            xtitle=f"X [{length_unit}]",
            ytitle=f"Y [{length_unit}]",
            ztitle=f"Z [{length_unit}]",
        )
        plotter.view_isometric()
        plotter.show(
            title=(
                f'Interactive 3D Results: "{chosen.name}"  ' f"(displacement scale: {displacement_scale}×)"
            )
        )

    def plot_model(
        self,
        plane: str = "yz",
        show_supports: bool = True,
        annotate_supports: bool = True,
        support_marker_size: int = 60,
        support_marker_facecolor: str = "black",
        support_marker_edgecolor: str = "white",
        support_annotation_fontsize: int = 8,
        support_annotation_offset_xy: tuple[int, int] = (6, 6),
        show_nodes_points: bool = True,
        node_point_size: int = 10,
        member_line_width: float = 1.5,
        member_color: str = "tab:blue",
        node_color: str = "tab:red",
        equal_aspect: bool = False,
    ):
        """
        Plot the model in 2D using GLOBAL coordinates (no normalization or shifts).
        Members, nodes, and supports are all projected from their raw XYZ positions
        into the chosen plane.
        """

        from collections import defaultdict

        # bring in your helpers
        from fers_core.supports.support_utils import (
            get_condition_type,
            color_for_condition_type,
            format_support_short,
        )

        def project_xyz_to_plane(
            X_value: float, Y_value: float, Z_value: float, plane_name: str
        ) -> tuple[float, float]:
            plane_lower = plane_name.lower()
            if plane_lower == "xy":
                return X_value, Y_value
            if plane_lower == "xz":
                return X_value, Z_value
            if plane_lower == "yz":
                return Y_value, Z_value
            raise ValueError("plane must be one of 'xy', 'xz', 'yz'")

        def axis_labels_for_plane(plane_name: str) -> tuple[str, str]:
            plane_lower = plane_name.lower()
            if plane_lower == "xy":
                return "X", "Y"
            if plane_lower == "xz":
                return "X", "Z"
            if plane_lower == "yz":
                return "Y", "Z"
            raise ValueError("plane must be one of 'xy', 'xz', 'yz'")

        def in_plane_axes(plane_name: str) -> tuple[str, str]:
            return axis_labels_for_plane(plane_name)

        def marker_for_support_on_plane(support, plane_name: str) -> str:
            """
            Plane-aware marker describing in-plane translational restraint.
            Mapping:
            - both in-plane fixed            -> 's'
            - only first plotted axis fixed  -> '|'
            - only second plotted axis fixed -> '_'
            - any spring in-plane            -> 'D'
            - otherwise                      -> 'o'
            """
            axis_one, axis_two = in_plane_axes(plane_name)
            condition_one = get_condition_type((support.displacement_conditions or {}).get(axis_one))
            condition_two = get_condition_type((support.displacement_conditions or {}).get(axis_two))

            is_fixed_one = condition_one == "fixed"
            is_fixed_two = condition_two == "fixed"
            is_spring_one = condition_one == "spring"
            is_spring_two = condition_two == "spring"

            if is_fixed_one and is_fixed_two:
                return "s"
            if is_fixed_one and not is_fixed_two:
                return "|"
            if is_fixed_two and not is_fixed_one:
                return "_"
            if is_spring_one or is_spring_two:
                return "D"
            return "o"

        def in_plane_condition_summary(support, plane_name: str) -> str:
            """
            Summarize in-plane displacement to select a color:
            - 'fixed'  if both plotted axes fixed
            - 'free'   if both plotted axes free
            - 'spring' if any plotted axis spring
            - 'mixed'  otherwise
            """
            axis_one, axis_two = in_plane_axes(plane_name)
            condition_one = get_condition_type((support.displacement_conditions or {}).get(axis_one))
            condition_two = get_condition_type((support.displacement_conditions or {}).get(axis_two))
            if condition_one == "fixed" and condition_two == "fixed":
                return "fixed"
            if condition_one == "free" and condition_two == "free":
                return "free"
            if condition_one == "spring" or condition_two == "spring":
                return "spring"
            return "mixed"

        # Collect global-projected geometry
        member_lines_projected: list[tuple[tuple[float, float], tuple[float, float]]] = []
        node_points_projected: list[tuple[float, float]] = []
        nodes_with_support: list[tuple[float, float, object]] = []

        for member_set in self.member_sets:
            for member in member_set.members:
                start_x, start_y = project_xyz_to_plane(
                    member.start_node.X, member.start_node.Y, member.start_node.Z, plane
                )
                end_x, end_y = project_xyz_to_plane(
                    member.end_node.X, member.end_node.Y, member.end_node.Z, plane
                )
                member_lines_projected.append(((start_x, start_y), (end_x, end_y)))

                node_points_projected.append((start_x, start_y))
                node_points_projected.append((end_x, end_y))

                if getattr(member.start_node, "nodal_support", None):
                    nodes_with_support.append((start_x, start_y, member.start_node))
                if getattr(member.end_node, "nodal_support", None):
                    nodes_with_support.append((end_x, end_y, member.end_node))

        # Deduplicate nodes
        node_points_projected = list(dict.fromkeys(node_points_projected))

        # Include any standalone nodes
        for node in self.get_all_nodes():
            px, py = project_xyz_to_plane(node.X, node.Y, node.Z, plane)
            if (px, py) not in node_points_projected:
                node_points_projected.append((px, py))
            if getattr(node, "nodal_support", None):
                nodes_with_support.append((px, py, node))

        # Deduplicate supports by projected point and node identity
        unique_supports: dict[tuple[float, float, int], tuple[float, float, object]] = {}
        for px, py, node in nodes_with_support:
            unique_supports[(px, py, id(node))] = (px, py, node)
        nodes_with_support = list(unique_supports.values())

        # Plot (global coordinates)
        figure, axes = plt.subplots()

        # Members
        for (x0, y0), (x1, y1) in member_lines_projected:
            axes.plot([x0, x1], [y0, y1], color=member_color, linewidth=member_line_width, zorder=2)

        # Nodes (optional)
        if show_nodes_points and node_points_projected:
            node_x_values = [p[0] for p in node_points_projected]
            node_y_values = [p[1] for p in node_points_projected]
            axes.scatter(
                node_x_values,
                node_y_values,
                s=node_point_size,
                c=node_color,
                marker="o",
                zorder=3,
                label="Nodes",
                edgecolors="none",
            )

        # Supports (global coordinates, plane-aware)
        if show_supports and nodes_with_support:
            grouped_points_by_marker: dict[str, list[tuple[float, float, object]]] = defaultdict(list)
            for px, py, node in nodes_with_support:
                marker_symbol = marker_for_support_on_plane(node.nodal_support, plane)
                grouped_points_by_marker[marker_symbol].append((px, py, node))

            legend_added = False
            for marker_symbol, items in grouped_points_by_marker.items():
                xs = [item[0] for item in items]
                ys = [item[1] for item in items]
                face_colors = [
                    color_for_condition_type(in_plane_condition_summary(node.nodal_support, plane))
                    for _, _, node in items
                ]
                axes.scatter(
                    xs,
                    ys,
                    s=support_marker_size,
                    marker=marker_symbol,
                    c=face_colors,
                    edgecolors=support_marker_edgecolor,
                    linewidths=0.5,
                    zorder=5,
                    label="Nodal Supports (in-plane)" if not legend_added else None,
                )
                legend_added = True

                if annotate_supports:
                    for px, py, node in items:
                        # Use YOUR short-name formatter (Fx, Fr, k, +, -)
                        label_text = format_support_short(node.nodal_support)
                        axes.annotate(
                            label_text,
                            (px, py),
                            textcoords="offset points",
                            xytext=support_annotation_offset_xy,
                            fontsize=support_annotation_fontsize,
                            color="black",
                            zorder=6,
                        )

        # Axes labels and limits (global)
        label_x, label_y = axis_labels_for_plane(plane)
        axes.set_xlabel(label_x)
        axes.set_ylabel(label_y)

        min_coords, max_coords = self.get_structure_bounds()
        if min_coords is not None and max_coords is not None:
            if plane.lower() == "xy":
                min_x, max_x = min_coords[0], max_coords[0]
                min_y, max_y = min_coords[1], max_coords[1]
            elif plane.lower() == "xz":
                min_x, max_x = min_coords[0], max_coords[0]
                min_y, max_y = min_coords[2], max_coords[2]
            elif plane.lower() == "yz":
                min_x, max_x = min_coords[1], max_coords[1]
                min_y, max_y = min_coords[2], max_coords[2]
            else:
                raise ValueError("plane must be one of 'xy', 'xz', 'yz'")

            span_x = max(1e-9, max_x - min_x)
            span_y = max(1e-9, max_y - min_y)
            margin_x = 0.02 * span_x
            margin_y = 0.02 * span_y
            axes.set_xlim(min_x - margin_x, max_x + margin_x)
            axes.set_ylim(min_y - margin_y, max_y + margin_y)

        if equal_aspect:
            axes.set_aspect("equal", adjustable="box")

        axes.legend(loc="best")
        axes.set_title(f"Model Plot in Global Coordinates ({plane.upper()} view)")
        figure.tight_layout()
        plt.show()

    def get_model_summary(self):
        """Returns a summary of the model's components: MemberSets, LoadCases, and LoadCombinations."""
        summary = {
            "MemberSets": [member_set.id for member_set in self.member_sets],  # fixed
            "LoadCases": [load_case.name for load_case in self.load_cases],
            "LoadCombinations": [load_combination.name for load_combination in self.load_combinations],
        }
        return summary

    @staticmethod
    def create_member_set(
        start_point: Node,
        end_point: Node,
        section: Section,
        intermediate_points: list[Node] = None,
        classification: str = "",
        rotation_angle=None,
        chi=None,
        reference_member=None,
        l_y=None,
        l_z=None,
    ):
        members = []
        node_list = [start_point] + (intermediate_points or []) + [end_point]

        for i, node in enumerate(node_list[:-1]):
            start_node = node
            end_node = node_list[i + 1]
            member = Member(
                start_node=start_node,
                end_node=end_node,
                section=section,
                classification=classification,
                rotation_angle=rotation_angle,
                chi=chi,
                reference_member=reference_member,
            )
            members.append(member)

        member_set = MemberSet(members=members, classification=classification, l_y=l_y, l_z=l_z)
        return member_set

    @staticmethod
    def combine_member_sets(*member_sets):
        combined_members = []
        for member_set in member_sets:
            # Assuming .members is a list of Member objects in each MemberSet
            combined_members.extend(member_set.members)

        combined_member_set = MemberSet(members=combined_members)
        return combined_member_set

    def get_model_renderer(self) -> ModelRenderer:
        """Create and return a ModelRenderer instance for this model.

        This provides access to the modular visualization system where each
        element (Node, Member, etc.) defines its own rendering.

        Returns:
            ModelRenderer: Configured renderer for the model structure

        Example:
            >>> renderer = model.get_model_renderer()
            >>> renderer.render_nodes = True
            >>> renderer.render_supports = True
            >>> renderer.show()
        """
        from fers_core.visualization.model_renderer import ModelRenderer

        return ModelRenderer(self)

    def get_result_renderer(self) -> ResultRenderer:
        """Create and return a ResultRenderer instance for this model.

        This provides access to the modular result visualization system for
        displaying deformed shapes, diagrams, and contours.

        Returns:
            ResultRenderer: Configured renderer for analysis results

        Example:
            >>> renderer = model.get_result_renderer()
            >>> renderer.deformed_shape = True
            >>> renderer.deformed_scale = 50.0
            >>> renderer.member_diagrams = 'My'
            >>> renderer.show()
        """
        from fers_core.visualization.result_renderer import ResultRenderer

        return ResultRenderer(self)

    # ── FersCloud integration ───────────────────────────

    _cloud_client: Optional["FersCloudClient"] = None

    def cloud_login(
        self,
        email: str,
        password: str,
        base_url: str = "https://ferscloud.com",
    ) -> dict:
        """Authenticate with FersCloud and obtain a 1-hour SDK token.

        After a successful login the token is cached on the FERS instance
        so that subsequent ``cloud_save`` / ``cloud_load`` calls work
        without re-authenticating.

        Parameters
        ----------
        email : str
            Your FersCloud account email.
        password : str
            Your FersCloud account password.
        base_url : str
            Override the FersCloud URL (use ``http://localhost:3000``
            for local development).

        Returns
        -------
        dict
            Token info including ``is_premium`` and ``expires_at``.

        Example
        -------
        >>> model = FERS()
        >>> model.cloud_login("you@example.com", "s3cret")
        """
        from fers_core.cloud import FersCloudClient

        self._cloud_client = FersCloudClient(base_url=base_url)
        return self._cloud_client.login(email, password)

    def cloud_connect(
        self,
        api_key: str,
        base_url: str = "https://ferscloud.com",
    ) -> dict:
        """Authenticate with FersCloud using a persistent API key.

        API keys are created in your FersCloud profile or via the
        SDK API.  They persist until revoked and do not expire
        after 1 hour like email/password tokens.

        Parameters
        ----------
        api_key : str
            A FersCloud API key in ``{keyId}.{secret}`` format.
        base_url : str
            Override the FersCloud URL (use ``http://localhost:3000``
            for local development).

        Returns
        -------
        dict
            User information: ``user_id``, ``email``, ``is_premium``.

        Example
        -------
        >>> model = FERS()
        >>> model.cloud_connect("clxyz123.AbCdEfGhIjKlMnOpQrStUvWx")
        """
        from fers_core.cloud import FersCloudClient

        self._cloud_client = FersCloudClient(base_url=base_url)
        return self._cloud_client.connect(api_key)

    def _ensure_cloud(self) -> FersCloudClient:
        if self._cloud_client is None or not self._cloud_client.is_authenticated:
            raise RuntimeError(
                "Not authenticated with FersCloud. "
                "Call cloud_connect(api_key) or cloud_login(email, password) first."
            )
        return self._cloud_client

    def cloud_save(
        self,
        name: str,
        description: str | None = None,
        include_results: bool = False,
    ) -> dict:
        """Save this FERS model to FersCloud.

        Parameters
        ----------
        name : str
            A display name for the saved model.
        description : str, optional
            An optional description.
        include_results : bool
            Whether to include analysis results in the saved JSON.
            Defaults to ``False`` (model geometry + loads only).

        Returns
        -------
        dict
            Created model metadata (``id``, ``name``, etc.).

        Example
        -------
        >>> model.cloud_login("you@example.com", "s3cret")
        >>> info = model.cloud_save("My Bridge")
        >>> print(info["id"])
        """
        client = self._ensure_cloud()
        return client.save_model(
            name,
            self.to_dict(include_results=include_results),
            description=description,
        )

    @classmethod
    def cloud_load(
        cls,
        model_id: str,
        cloud_client: "FersCloudClient",
    ) -> "FERS":
        """Load a FERS model from FersCloud by its ID.

        Parameters
        ----------
        model_id : str
            The cloud model ID.
        cloud_client : FersCloudClient
            An authenticated ``FersCloudClient`` instance.  You can obtain
            one from an existing FERS instance via ``model._cloud_client``
            or by creating one directly.

        Returns
        -------
        FERS
            A fully reconstructed FERS instance.

        Example
        -------
        >>> cloud = FersCloudClient("http://localhost:3000")
        >>> cloud.login("you@example.com", "s3cret")
        >>> model = FERS.cloud_load("clx123abc", cloud)
        """
        data = cloud_client.load_model(model_id)
        model_dict = data["model"]
        instance = cls.from_dict(model_dict)
        instance._cloud_client = cloud_client
        return instance

    def cloud_list(self) -> list[dict]:
        """List all cloud models for the authenticated user.

        Returns
        -------
        list[dict]
            Each dict has ``id``, ``name``, ``description``,
            ``createdAt``, ``updatedAt``.
        """
        client = self._ensure_cloud()
        return client.list_models()

    def cloud_delete(self, model_id: str) -> None:
        """Delete a cloud model by its ID.

        Parameters
        ----------
        model_id : str
            The cloud model ID to delete.
        """
        client = self._ensure_cloud()
        client.delete_model(model_id)

    def cloud_update(
        self,
        model_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        include_results: bool = False,
    ) -> dict:
        """Update an existing cloud model with the current state.

        Parameters
        ----------
        model_id : str
            The cloud model ID to update.
        name : str, optional
            New display name.
        description : str, optional
            New description.
        include_results : bool
            Whether to include analysis results.

        Returns
        -------
        dict
            Updated model metadata.
        """
        client = self._ensure_cloud()
        return client.update_model(
            model_id,
            name=name,
            description=description,
            model_dict=self.to_dict(include_results=include_results),
        )
