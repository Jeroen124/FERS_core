import re
from typing import Dict, Optional, Tuple, Union
import fers_calculations
import ujson

import numpy as np
import matplotlib.pyplot as plt
import pyvista as pv


from ..fers.deformation_utils import (
    interpolate_beam_local,
    transform_dofs_global_to_local,
    extrude_along_path,
)
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
from ..types.pydantic_models import Results, ResultsBundle


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
        self.results = None

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
            results_dict = ujson.loads(result_string)
            validated_results = ResultsBundle(**results_dict)
            self.results = validated_results
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
            results_dict = ujson.loads(result_string)
            validated_results = ResultsBundle(**results_dict)
            self.results = validated_results
        except Exception as e:
            raise ValueError(f"Failed to parse or validate results: {e}")

    def to_dict(self):
        """Convert the FERS model to a dictionary representation."""
        return {
            "member_sets": [member_set.to_dict() for member_set in self.member_sets],
            "load_cases": [load_case.to_dict() for load_case in self.load_cases],
            "load_combinations": [load_comb.to_dict() for load_comb in self.load_combinations],
            "imperfection_cases": [imp_case.to_dict() for imp_case in self.imperfection_cases],
            "settings": self.settings.to_dict(),
            "results": self.results.to_dict() if self.results else None,
            "memberhinges": [
                memberhinge.to_dict() for memberhinge in self.get_unique_member_hinges_from_all_member_sets()
            ],
            "materials": [
                material.to_dict() for material in self.get_unique_materials_from_all_member_sets()
            ],
            "sections": [section.to_dict() for section in self.get_unique_sections_from_all_member_sets()],
            "nodal_supports": [
                nodal_support.to_dict()
                for nodal_support in self.get_unique_nodal_support_from_all_member_sets()
            ],
            "shape_paths": [
                shape_path.to_dict() for shape_path in self.get_unique_shape_paths_from_all_member_sets()
            ],
        }

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

        Args:
            member_set (MemberSet): The member set to be translated.
            translation_vector (tuple): The translation vector (dx, dy, dz).

        Returns:
            MemberSet: A new MemberSet instance with translated members.
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
                material=member.section.material,
                classification=member.classification,
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

        Args:
            model (FERS): The model to be translated.
            translation_vector (tuple): A tuple (dx, dy, dz) representing the translation vector.

        Returns:
            FERS: A new model instance with translated nodes.
        """
        new_model = FERS()  # Assuming FERS is your model class
        node_translation_map = {}  # Map original nodes to their translated versions

        # Translate all nodes
        for original_node in model.get_all_nodes():
            translated_node = Node(
                X=original_node.X + translation_vector[0],
                Y=original_node.Y + translation_vector[1],
                Z=original_node.Z + translation_vector[2],
            )
            node_translation_map[original_node.id] = translated_node

        # Reconstruct member sets with translated nodes
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
                )
                new_members.append(new_member)
            new_member_set = MemberSet(
                members=new_members,
                classification=original_member_set.classification,
                member_set_id=original_member_set.member_set_id,
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

    def get_unique_materials_from_all_member_sets(self, ids_only=False):
        """
        Collects and returns unique materials used across all member sets in the model.

        Args:
            ids_only (bool): If True, return only the unique material IDs. Otherwise, return material objects.

        Returns:
            list: List of unique materials or material IDs used across all member sets.
        """
        unique_materials = set()
        for member_set in self.member_sets:
            materials = member_set.get_unique_materials(ids_only=ids_only)
            unique_materials.update(materials)
        return list(unique_materials)

    def get_unique_shape_paths_from_all_member_sets(self, ids_only=False):
        """
        Collects and returns unique ShapePath instances used across all member sets in the model.

        Args:
            ids_only (bool): If True, return only the unique ShapePath IDs.
                            Otherwise, return ShapePath objects.

        Returns:
            list: List of unique ShapePath instances or their IDs used across all member sets.
        """
        unique_shape_paths = {}

        for member_set in self.member_sets:
            for member in member_set.members:
                section = member.section
                if section.shape_path:
                    shape_path_id = section.shape_path.id
                    if shape_path_id not in unique_shape_paths:
                        unique_shape_paths[shape_path_id] = section.shape_path

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

    def get_unique_sections_from_all_member_sets(self, ids_only=False):
        """
        Collects and returns unique sections used across all member sets in the model.

        Args:
            ids_only (bool): If True, return only the unique section IDs. Otherwise, return section objects.

        Returns:
            list: List of unique sections or section IDs used across all member sets.
        """
        unique_sections = set()
        for member_set in self.member_sets:
            sections = member_set.get_unique_sections(ids_only=ids_only)
            unique_sections.update(sections)
        return list(unique_sections)

    def get_unique_member_hinges_from_all_member_sets(self, ids_only=False):
        """
        Collects and returns unique member hinges used across all member sets in the model.

        Args:
            ids_only (bool): If True, return only the unique hinge IDs. Otherwise, return hinge objects.

        Returns:
            list: List of unique hinges or hinge IDs used across all member sets.
        """
        unique_hinges = set()
        for member_set in self.member_sets:
            hinges = member_set.get_unique_memberhinges(ids_only=ids_only)
            unique_hinges.update(hinges)
        return list(unique_hinges)

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
        """Returns a set of unique material names used in the model."""
        unique_materials = set()
        for member_set in self.member_sets:
            for member in member_set.members:
                unique_materials.add(member.section.material.name)
        return unique_materials

    def get_unique_section_names(self):
        """Returns a set of unique section names used in the model."""
        unique_sections = set()
        for member_set in self.member_sets:
            for member in member_set.members:
                unique_sections.add(member.section.name)
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

    def get_unique_nodal_support(self):
        """
        Returns a set of unique sections used in the model, identified by their names.
        """
        unique_nodal_supports = {}  # Use a dictionary to avoid duplicates based on material name

        for member_set in self.member_sets:
            for member in member_set.members:
                for node in [member.start_node, member.end_node]:
                    if node.nodal_support:
                        if node.nodal_support.id not in unique_nodal_supports:
                            unique_nodal_supports[node.id] = node.nodal_support

        # Return the materials as a list
        return unique_nodal_supports

    def get_unique_nodal_supports(self):
        """
        Returns a detailed mapping of all unique NodalSupport instances, including the numbers of all nodes
        that have each nodal support, and their displacement and rotation conditions.

        The return format is a list of dictionaries, each containing:
        - 'support_no': The unique identifier of the NodalSupport.
        - 'node_nos': A list of node numbers that share this NodalSupport.
        - 'displacement_conditions': Displacement conditions of the NodalSupport.
        - 'rotation_conditions': Rotation conditions of the NodalSupport.
        """
        support_details = {}

        for member_set in self.member_sets:
            for member in member_set.members:
                for node in [member.start_node, member.end_node]:
                    if node.nodal_support:
                        support_no = node.nodal_support.id
                        if support_no not in support_details:
                            support_details[support_no] = {
                                "support_no": support_no,
                                "node_nos": set(),
                                "displacement_conditions": node.nodal_support.displacement_conditions,
                                "rotation_conditions": node.nodal_support.rotation_conditions,
                            }
                        # Add the node's number to the list of nodes for this NodalSupport
                        support_details[support_no]["node_nos"].add(node.id)

        # Convert the details to a list of dictionaries for easier consumption
        detailed_support_list = list(support_details.values())

        return detailed_support_list

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
        show_nodes=True,
        show_sections=True,
        show_local_axes=False,
        display_Local_axes_scale=1,
        load_case=None,
        display_load_scale=1,  # Added scale factor for point loads, default = 1
        show_load_labels=True,
    ):
        """
        Creates an interactive 3D PyVista plot of the entire model, aligning sections to the member's axis.
        Parameters:
        - show_nodes (bool): Whether to show node spheres in the plot.
        - show_sections (bool): Whether to extrude sections along members' axes.
        - show_local_axes (bool): Whether to plot the local coordinate system at each member's start node.
        - load_case_name (str): Name of the load case to display loads for. If None, no point loads are shown.
        - point_load_scale (float): Scale factor for point loads, default is 1.
        """

        # Create a PyVista plotter
        plotter = pv.Plotter()

        # Store all members and lines
        all_points = []
        all_lines = []
        point_offset = 0

        # Retrieve all members
        members = self.get_all_members()

        min_coords, max_coords = self.get_structure_bounds()
        if min_coords and max_coords:
            structure_size = np.linalg.norm(np.array(max_coords) - np.array(min_coords))
        else:
            structure_size = 1.0

        arrow_scale_factor = structure_size * 0.5

        # Process all members to create 3D edges
        for member in members:
            start_node = member.start_node
            end_node = member.end_node

            # Collect start and end coordinates
            start_xyz = (start_node.X, start_node.Y, start_node.Z)
            end_xyz = (end_node.X, end_node.Y, end_node.Z)

            # Add points to the points list
            all_points.append(start_xyz)
            all_points.append(end_xyz)

            # Define a line connecting these two points
            all_lines.append(2)
            all_lines.append(point_offset)
            all_lines.append(point_offset + 1)

            point_offset += 2

        # Convert points and lines to PyVista PolyData
        all_points = np.array(all_points, dtype=np.float32)
        poly_data = pv.PolyData(all_points)
        poly_data.lines = np.array(all_lines, dtype=np.int32)

        # Add lines to the plot
        plotter.add_mesh(poly_data, color="blue", line_width=2, label="Members")

        if show_sections:
            for member in members:
                start_node = member.start_node
                end_node = member.end_node
                section = member.section

                if section.shape_path is not None:
                    # Get nodes and edges of the section in the local y-z plane
                    coords_2d, edges = section.shape_path.get_shape_geometry()

                    # Convert to a 3D format, keeping points in the local y-z plane
                    coords_local = np.array([[0.0, y, z] for y, z in coords_2d], dtype=np.float32)

                    # Get the local coordinate system
                    local_x, local_y, local_z = member.local_coordinate_system()

                    # Build the transformation matrix
                    transform_matrix = np.column_stack((local_x, local_y, local_z))

                    # Transform the local y-z points into the global coordinate system
                    transformed_coords = coords_local @ transform_matrix.T

                    # Translate the transformed coordinates to the start node position
                    transformed_coords += np.array([start_node.X, start_node.Y, start_node.Z])

                    # Create a PyVista PolyData for the section
                    section_polydata = pv.PolyData(transformed_coords)
                    lines = []
                    for edge in edges:
                        lines.append(2)
                        lines.extend(edge)
                    section_polydata.lines = np.array(lines, dtype=np.int32)

                    # Extrude the section along the member's local x-axis
                    dx = end_node.X - start_node.X
                    dy = end_node.Y - start_node.Y
                    dz = end_node.Z - start_node.Z
                    extruded_section = section_polydata.extrude([dx, dy, dz], capping=True)

                    # Add extruded section to the plot
                    plotter.add_mesh(extruded_section, color="steelblue", label=f"Section {section.name}")

        if show_local_axes:
            for index, member in enumerate(members):
                start_node = member.start_node
                local_x, local_y, local_z = member.local_coordinate_system()

                origin = np.array([start_node.X, start_node.Y, start_node.Z])
                scale = display_Local_axes_scale

                if index == 0:
                    plotter.add_arrows(origin, local_x * scale, color="red", label="Local X")
                    plotter.add_arrows(origin, local_y * scale, color="green", label="Local Y")
                    plotter.add_arrows(origin, local_z * scale, color="blue", label="Local Z")
                else:
                    plotter.add_arrows(origin, local_x * scale, color="red")
                    plotter.add_arrows(origin, local_y * scale, color="green")
                    plotter.add_arrows(origin, local_z * scale, color="blue")

        if load_case:
            load_case = self.get_load_case_by_name(load_case)
            if load_case:
                for nodal_load in load_case.nodal_loads:
                    node = nodal_load.node
                    # Compute the force vector components
                    load_vector = np.array(nodal_load.direction) * nodal_load.magnitude * display_load_scale
                    magnitude = np.linalg.norm(load_vector)
                    if magnitude > 0:
                        direction = load_vector / magnitude
                        plotter.add_arrows(
                            np.array([node.X, node.Y, node.Z]),
                            direction * arrow_scale_factor,  # Scale arrows
                            color="#FFA500",  # Orange
                            label="Point Load",
                        )
                        # Calculate the midpoint for the label position
                        midpoint = np.array([node.X, node.Y, node.Z]) + (direction * (arrow_scale_factor / 2))
                        # Display the magnitude next to the midpoint of the arrow
                        plotter.add_point_labels(
                            midpoint,
                            [f"{magnitude:.2f}"],  # Format magnitude to 2 decimal places
                            font_size=20 * arrow_scale_factor,
                            text_color="#FFA500",
                            always_visible=show_load_labels,
                        )

        if show_nodes:
            # Plot spheres at each unique node location
            unique_nodes = self.get_all_nodes()
            node_points = np.array([(node.X, node.Y, node.Z) for node in unique_nodes], dtype=np.float32)
            point_cloud = pv.PolyData(node_points)
            glyph = point_cloud.glyph(geom=pv.Sphere(radius=0.1), scale=False, orient=False)
            plotter.add_mesh(glyph, color="red", label="Nodes")

        # Add a legend and grid
        plotter.add_legend()
        min_coords, max_coords = self.get_structure_bounds()
        if min_coords and max_coords:
            margin = 0.5  # meters, adjust to taste
            x_min, y_min, z_min = (c - margin for c in min_coords)
            x_max, y_max, z_max = (c + margin for c in max_coords)
            plotter.show_grid(bounds=[x_min, x_max, y_min, y_max, z_min, z_max], color="gray")
        else:
            plotter.show_grid(color="gray")
        plotter.show(title="FERS 3D Model")

    def show_results_3d(
        self,
        *,
        loadcase: Optional[Union[int, str]] = None,
        loadcombination: Optional[Union[int, str]] = None,
        show_nodes: bool = True,
        show_sections: bool = True,
        displacement: bool = True,
        displacement_scale: float = 100.0,
        num_points: int = 20,
    ):
        """
        Visualizes any one of the loaded cases or combinations in 3D using PyVista.

        Args:
            loadcase (int or str, optional): If you want a load‑case, specify either its
                one‑based index (1, 2, …) or its name ("Dead Load", "End Load", …).
            loadcombination (int or str, optional): Likewise for load‑combinations.
            show_sections (bool): Extrude and draw section profiles.
            show_nodes (bool): Draw the nodes as spheres.
            displacement (bool): Show the deformed shape as well as the original.
            displacement_scale (float): How much to scale nodal displacements.
            num_points (int): Number of points per member for interpolation.
        """
        # pick the right Results object out of the Bundle
        bundle = self.results  # assume this is a ResultsBundle
        chosen: Results
        if loadcase is not None and loadcombination is not None:
            raise ValueError("Please specify either loadcase or loadcombination, not both.")
        if loadcase is not None:
            keys = list(bundle.loadcases.keys())
            if isinstance(loadcase, int):
                try:
                    key = keys[loadcase - 1]
                except IndexError:
                    raise IndexError(f"Loadcase index {loadcase} is out of range.")
            else:
                key = loadcase
                if key not in bundle.loadcases:
                    raise KeyError(f"Loadcase '{key}' not found.")
            chosen = bundle.loadcases[key]
        elif loadcombination is not None:
            keys = list(bundle.loadcombinations.keys())
            if isinstance(loadcombination, int):
                try:
                    key = keys[loadcombination - 1]
                except IndexError:
                    raise IndexError(f"Loadcombination index {loadcombination} is out of range.")
            else:
                key = loadcombination
                if key not in bundle.loadcombinations:
                    raise KeyError(f"Loadcombination '{key}' not found.")
            chosen = bundle.loadcombinations[key]
        else:
            # neither was given: if there's exactly one loadcase and zero combinations, take it
            if len(bundle.loadcases) == 1 and not bundle.loadcombinations:
                chosen = next(iter(bundle.loadcases.values()))
            else:
                raise ValueError(
                    "Multiple results available – please specify " "`loadcase=` or `loadcombination=`."
                )

        # now 'chosen' is a Results object; pull out exactly what you need
        displacement_nodes = chosen.displacement_nodes

        # ---------------------------------------------------
        # HELPER FUNCTIONS TO REMOVE DUPLICATION
        # ---------------------------------------------------
        def get_local_transform(member):
            lx, ly, lz = member.local_coordinate_system()
            return np.column_stack([lx, ly, lz])

        def interpolate_member(member, d_start, r_start, d_end, r_end):
            L = member.length()
            local_deflections = interpolate_beam_local(
                0.0,
                L,
                d_start,
                d_end,
                r_start,
                r_end,
                num_points,
            )
            return local_deflections * displacement_scale

        def plot_section(member, d_start_vec, r_start_vec, d_end_vec, r_end_vec):
            # build the section polydata once
            section = member.section
            if section.shape_path is None:
                return

            coords_2d, edges = section.shape_path.get_shape_geometry()
            coords_local = np.array([[0.0, y, z] for y, z in coords_2d], dtype=np.float32)
            R = get_local_transform(member)

            # original
            start = member.start_node
            end = member.end_node
            origin = np.array([start.X, start.Y, start.Z])
            coords_global = (coords_local @ R.T + origin).astype(np.float32)
            pd = pv.PolyData(coords_global)
            line_array = []
            for a, b in edges:
                line_array.extend((2, a, b))
            pd.lines = np.array(line_array, dtype=np.int32)
            direction = np.array([end.X, end.Y, end.Z]) - origin
            orig_extruded = pd.extrude(direction, capping=True)
            plotter.add_mesh(orig_extruded, color="steelblue", label=f"Section {section.name}")

            # deformed
            if displacement:
                # transform global → local
                dls, rls = transform_dofs_global_to_local(d_start_vec, r_start_vec, R)
                dle, rle = transform_dofs_global_to_local(d_end_vec, r_end_vec, R)
                local_def = interpolate_member(member, dls, rls, dle, rle)

                # build the deformed path in global coords
                t_vals = np.linspace(0, 1, num_points)
                curve_pts = []
                for i, t in enumerate(t_vals):
                    orig_pt = origin + t * direction
                    defl_local = local_def[i]
                    defl_global = R @ defl_local
                    curve_pts.append(orig_pt + defl_global)
                curve_pts = np.array(curve_pts)

                spline = pv.Spline(curve_pts, num_points * 2)
                if not isinstance(spline, pv.PolyData):
                    raise ValueError("Extrusion path invalid.")
                deformed = extrude_along_path(section.shape_path, spline.points)
                plotter.add_mesh(deformed, color="red", label=f"Deformed Section {section.name}")

        # ---------------------------------------------------
        # START DRAWING
        # ---------------------------------------------------
        plotter = pv.Plotter()
        plotter.add_axes()

        # precompute all nodal positions and displacements
        node_pos: Dict[int, np.ndarray] = {}
        node_disp: Dict[int, Tuple[np.ndarray, np.ndarray]] = {}
        for nid_str, nodisp in displacement_nodes.items():
            nid = int(nid_str)
            node = self.get_node_by_pk(nid)
            if node is None:
                continue
            pos = np.array([node.X, node.Y, node.Z])
            node_pos[nid] = pos
            if displacement and nodisp:
                dgl = np.array([nodisp.dx, nodisp.dy, nodisp.dz])
                rgl = np.array([nodisp.rx, nodisp.ry, nodisp.rz])
            else:
                dgl = np.zeros(3)
                rgl = np.zeros(3)
            node_disp[nid] = (dgl, rgl)

        if show_sections:
            for member in self.get_all_members():
                ds, rs = node_disp[member.start_node.id]
                de, re = node_disp[member.end_node.id]
                plot_section(member, ds, rs, de, re)

        if show_nodes:
            originals = []
            deformed = []
            for node in self.get_all_nodes():
                pid = node.id
                orig = np.array([node.X, node.Y, node.Z])
                originals.append(orig)
                dgl, _ = node_disp.get(pid, (np.zeros(3), None))
                deformed.append(orig + dgl * displacement_scale)
            originals = np.array(originals)
            deformed = np.array(deformed)

            plotter.add_mesh(
                pv.PolyData(originals).glyph(scale=False, geom=pv.Sphere(radius=0.05)),
                color="blue",
                label="Original Nodes",
            )
            plotter.add_mesh(
                pv.PolyData(deformed).glyph(scale=False, geom=pv.Sphere(radius=0.05)),
                color="red",
                label="Deformed Nodes",
            )

        # finally each member’s center‐line
        for member in self.get_all_members():
            start_id = member.start_node.id
            end_id = member.end_node.id
            p0 = node_pos[start_id]
            p1 = node_pos[end_id]
            d0, r0 = node_disp[start_id]
            d1, r1 = node_disp[end_id]

            R = get_local_transform(member)
            local_def = interpolate_member(
                member, *transform_dofs_global_to_local(d0, r0, R), *transform_dofs_global_to_local(d1, r1, R)
            )
            t_vals = np.linspace(0, 1, num_points)
            orig_curve = np.array([p0 + t * (p1 - p0) for t in t_vals])
            def_curve = np.array([orig_curve[i] + (R @ local_def[i]) for i in range(num_points)])

            plotter.add_lines(orig_curve, color="blue", width=2, label="Original Shape")
            plotter.add_lines(def_curve, color="red", width=2, label="Deformed Shape")

        plotter.add_legend()
        plotter.show_grid(color="gray")
        plotter.show(title=f"3D Results: “{chosen.name}”")

    def plot_model(self, plane="yz"):
        """
        Plot all member sets in the model on the specified plane.

        Parameters:
        - plane: A string specifying the plot plane, either 'xy', 'xz', or 'yz'.
        """
        # Create a single figure and axis for all plots
        fig, ax = plt.subplots()

        # Loop through all member sets and plot them on the same figure
        for member_set in self.member_sets:
            member_set.plot(
                plane=plane, fig=fig, ax=ax, set_aspect=False, show_title=False, show_legend=False
            )

        ax.set_title("Combined Model Plot")
        # ax.legend()
        plt.tight_layout()
        plt.show()

    def get_model_summary(self):
        """Returns a summary of the model's components: MemberSets, LoadCases, and LoadCombinations."""
        summary = {
            "MemberSets": [member_set.id for member_set in self.member_sets],
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
