import re
import fers_calculations
import ujson

import numpy as np
import matplotlib.pyplot as plt
import pyvista as pv

from ..fers.deformation_utils import (
    get_rotation_matrix,
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
from ..types.pydantic_models import Results


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
            validated_results = Results(**results_dict)
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

        # Parse and validate the results
        try:
            results_dict = ujson.loads(result_string)  # Use ujson for performance
            validated_results = Results(**results_dict)  # Validate with Pydantic
            self.results = validated_results  # Update instance's results
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
        show_local_axes=True,
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
                    extruded_section = section_polydata.extrude([dx, dy, dz])

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
                            color="FFA500",  # Orange
                            label="Point Load",
                        )
                        # Calculate the midpoint for the label position
                        midpoint = np.array([node.X, node.Y, node.Z]) + (direction * (arrow_scale_factor / 2))
                        # Display the magnitude next to the midpoint of the arrow
                        plotter.add_point_labels(
                            midpoint,
                            [f"{magnitude:.2f}"],  # Format magnitude to 2 decimal places
                            font_size=20 * arrow_scale_factor,
                            text_color="FFA500",
                            always_visible=show_load_labels,
                        )

        if show_nodes:
            # Plot spheres at each unique node location
            unique_nodes = self.get_all_nodes()
            node_points = [(node.X, node.Y, node.Z) for node in unique_nodes]
            point_cloud = pv.PolyData(node_points)
            glyph = point_cloud.glyph(geom=pv.Sphere(radius=0.1), scale=False, orient=False)
            plotter.add_mesh(glyph, color="red", label="Nodes")

        # Add a legend and grid
        plotter.add_legend()
        plotter.show_grid(color="gray")
        plotter.show(title="FERS 3D Model")

    def show_results_3d(
        self, show_nodes=True, show_sections=True, displacement=True, displacement_scale=100.0, num_points=20
    ):
        """
        Visualizes the results of the analysis in 3D using PyVista, including displacements if enabled.
        Now updated to do local transformations for each member.

        Args:
            displacement (bool): Whether to show the displacement results.
            show_sections (bool): Whether to extrude sections along members' axes.
            show_nodes (bool): Whether to show node spheres in the plot.
            displacement_scale (float): Scale factor for visualizing displacements.
            num_points (int): Number of interpolation points along each member.
        """
        if self.results is None:
            print("No results to display. Please run an analysis first.")
            return

        # Extract nodes and their global displacements from the results
        displacement_nodes = self.results.displacement_nodes
        node_positions = {}
        node_displacements_global = {}

        for node_id_str, disp in displacement_nodes.items():
            node_id = int(node_id_str)
            node = self.get_node_by_pk(node_id)
            if node:
                original_position = np.array([node.X, node.Y, node.Z])
                node_positions[node_id] = original_position

                if disp and displacement:
                    # Global displacement vector
                    d_global = np.array([disp.dx, disp.dy, disp.dz])  # Displacements in m
                    r_global = np.array([disp.rx, disp.ry, disp.rz])  # rotations in rad

                else:
                    d_global = np.array([0.0, 0.0, 0.0])
                    r_global = np.array([0.0, 0.0, 0.0])

                node_displacements_global[node_id] = (d_global, r_global)

        # Create a PyVista plotter
        plotter = pv.Plotter()
        plotter.add_axes()  # 3D axes

        # Plot sections
        if show_sections:
            for member in self.get_all_members():
                start_node = member.start_node
                end_node = member.end_node
                section = member.section

                if section.shape_path is not None:
                    # Original section coordinates in local space
                    coords_2d, edges = section.shape_path.get_shape_geometry()
                    coords_local = np.array([[0.0, y, z] for y, z in coords_2d], dtype=np.float32)

                    # Get the local coordinate system
                    local_x, local_y, local_z = member.local_coordinate_system()
                    R = np.column_stack([local_x, local_y, local_z])  # Transformation matrix

                    # Transform and extrude for original shape
                    transformed_coords = coords_local @ R.T + np.array(
                        [start_node.X, start_node.Y, start_node.Z]
                    )
                    section_polydata = pv.PolyData(transformed_coords)
                    lines = []
                    for edge in edges:
                        lines.extend([2, edge[0], edge[1]])
                    section_polydata.lines = np.array(lines, dtype=np.int32)

                    dx, dy, dz = np.array([end_node.X, end_node.Y, end_node.Z]) - np.array(
                        [start_node.X, start_node.Y, start_node.Z]
                    )
                    original_section = section_polydata.extrude([dx, dy, dz])
                    plotter.add_mesh(original_section, color="steelblue", label=f"Section {section.name}")

                    # Deformed shape
                    if displacement:
                        # Get displacements at start and end nodes
                        d_global_start, r_global_start = node_displacements_global.get(
                            start_node.id, (np.zeros(3), None)
                        )
                        d_global_end, r_global_end = node_displacements_global.get(
                            end_node.id, (np.zeros(3), None)
                        )

                        # Local coordinate system and transformation matrix
                        local_x, local_y, local_z = member.local_coordinate_system()
                        R = np.column_stack([local_x, local_y, local_z])  # Transformation matrix

                        # Transform global displacements to local
                        d_local_start, r_local_start = transform_dofs_global_to_local(
                            d_global_start, r_global_start, R
                        )
                        d_local_end, r_local_end = transform_dofs_global_to_local(
                            d_global_end, r_global_end, R
                        )

                        # Interpolate along the beam
                        deflections_local = interpolate_beam_local(
                            0.0,
                            member.length(),
                            d_local_start,
                            d_local_end,
                            r_local_start,
                            r_local_end,
                            num_points,
                        )

                        # Generate the deformed curve in global space
                        deformed_curve_global = []
                        for i, t in enumerate(np.linspace(0, 1, num_points)):
                            # Original position along the beam axis
                            orig_pt_global = (1 - t) * np.array(
                                [start_node.X, start_node.Y, start_node.Z]
                            ) + t * np.array([end_node.X, end_node.Y, end_node.Z])

                            # Deformation in local coordinates
                            deflection_local = deflections_local[i]

                            # Transform local deflection to global
                            deflection_global = R @ deflection_local

                            # Deformed position in global space
                            deformed_curve_global.append(
                                orig_pt_global + deflection_global * displacement_scale
                            )

                        deformed_curve_global = np.array(deformed_curve_global)

                        # Extrude the section along the deformed curve
                        path_polydata = pv.Spline(deformed_curve_global, num_points * 2)
                        transformed_coords = coords_local @ R.T + np.array(
                            [start_node.X, start_node.Y, start_node.Z]
                        )
                        section_polydata = pv.PolyData(transformed_coords)
                        lines = []
                        for edge in edges:
                            lines.extend([2, edge[0], edge[1]])
                        section_polydata.lines = np.array(lines, dtype=np.int32)

                        if path_polydata is not None and isinstance(path_polydata, pv.PolyData):
                            path_points = path_polydata.points  # Extract Nx3 array of points
                            deformed_section = extrude_along_path(member.section.shape_path, path_points)
                        else:
                            raise ValueError(
                                "Invalid path for extrusion. Ensure path_polydata is a valid PolyData object."
                            )

                        print(path_polydata)
                        plotter.add_mesh(
                            deformed_section, color="red", label=f"Deformed Section {section.name}"
                        )

        # Plot nodes
        if show_nodes:
            unique_nodes = self.get_all_nodes()
            original_node_positions = []
            deformed_node_positions = []

            for node in unique_nodes:
                node_id = node.id
                original_position = np.array([node.X, node.Y, node.Z])
                original_node_positions.append(original_position)

                if node_id in node_displacements_global:
                    d_global, _ = node_displacements_global[node_id]
                    deformed_position = original_position + d_global * displacement_scale
                    deformed_node_positions.append(deformed_position)

            # Convert to numpy arrays
            original_node_positions = np.array(original_node_positions)
            deformed_node_positions = np.array(deformed_node_positions)

            # Plot original nodes as blue spheres
            plotter.add_mesh(
                pv.PolyData(original_node_positions).glyph(scale=False, geom=pv.Sphere(radius=0.05)),
                color="blue",
                label="Original Nodes",
            )

            # Plot deformed nodes as red spheres
            plotter.add_mesh(
                pv.PolyData(deformed_node_positions).glyph(scale=False, geom=pv.Sphere(radius=0.05)),
                color="red",
                label="Deformed Nodes",
            )

        # Now, loop over members and plot
        for member in self.get_all_members():
            # Original line in global
            start_id = member.start_node.id
            end_id = member.end_node.id

            start_pos_global = node_positions[start_id]
            end_pos_global = node_positions[end_id]

            # Grab the global disp & rotations
            d_global_start, r_global_start = node_displacements_global[start_id]
            d_global_end, r_global_end = node_displacements_global[end_id]

            # local axes
            local_x, local_y, local_z = member.local_coordinate_system()
            R = get_rotation_matrix(local_x, local_y, local_z)

            # 1) Transform the start/end DOFs to local
            d_local_start, r_local_start = transform_dofs_global_to_local(d_global_start, r_global_start, R)
            d_local_end, r_local_end = transform_dofs_global_to_local(d_global_end, r_global_end, R)

            # 2) The local "x" coordinate for the start node is 0, for the end node is member.length()
            #    We'll just say xstart=0, xend=L
            L = member.length()

            # 3) Interpolate the local deflection.
            #    local_disp_start = (u_x, u_y, u_z) at the start
            #    local_rot_start  = (phi_x, phi_y, phi_z) at the start, etc.
            local_disp_start = d_local_start
            local_disp_end = d_local_end
            local_rot_start = r_local_start
            local_rot_end = r_local_end

            deflections_local = interpolate_beam_local(
                0.0, L, local_disp_start, local_disp_end, local_rot_start, local_rot_end, num_points
            )
            deflections_local *= displacement_scale

            # shape (n_points, 3) => each row is [ux, uy, uz] in local coords

            # 4) Convert local deflections back to global
            #    But we also need the local coordinate of each point along the beam's axis in global space.
            #    A param s in [0..1],
            #    the global position = start_pos_global + s*(end_pos_global - start_pos_global).
            s_vals = np.linspace(0, 1, num_points)
            original_curve_global = []
            deformed_curve_global = []

            for i, s in enumerate(s_vals):
                # original global coordinate
                orig_pt = start_pos_global + s * (end_pos_global - start_pos_global)
                original_curve_global.append(orig_pt)

                # local deflection at this point
                defl_loc = deflections_local[i]

                # transform local deflection to global
                defl_g = R @ defl_loc

                # add the node's base position in global + deflection + (optionally scale factor)
                defl_pt_global = orig_pt + defl_g
                deformed_curve_global.append(defl_pt_global)

            original_curve_global = np.array(original_curve_global)
            deformed_curve_global = np.array(deformed_curve_global)

            # Plot original curve in BLUE
            plotter.add_lines(original_curve_global, color="blue", width=2, label="Original Shape")

            # Plot deformed curve in RED
            plotter.add_lines(deformed_curve_global, color="red", width=2, label="Deformed Shape")

        # Show
        plotter.add_legend()
        plotter.show_grid(color="gray")
        plotter.show(title="3D Beam Displacement Visualization (Local -> Global)")

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
