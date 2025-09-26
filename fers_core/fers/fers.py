import re
from typing import Dict, Optional, Tuple, Union
import fers_calculations
import ujson

import numpy as np
import matplotlib.pyplot as plt
import pyvista as pv

from fers_core.fers.deformation_utils import (
    extrude_along_path,
    interpolate_beam_local,
    transform_dofs_global_to_local,
)
from fers_core.supports.support_utils import (
    format_support_label,
    get_condition_type,
    format_support_short,
    choose_marker,
    color_for_condition_type,
    translational_summary,
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
from ..types.pydantic_models import ResultsBundle


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
                id=original_member_set.memberset_id,
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
        load_case: Optional[str] = None,
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
        - load_case: Name of load case to display loads.
        - display_load_scale: Scale factor for point loads.
        - show_load_labels: Show load magnitudes next to arrows.
        - show_supports: Draw nodal supports visualization.
        - show_support_labels: Add compact text label per support (U[...] R[...]).
        - support_size_fraction: Size of support arrows vs model bounding size.
        - show_support_base_for_fixed: If True, draw a flat square (plate) for
        all-fixed translational supports.
        """
        # -----------------------------
        # Build plot
        # -----------------------------
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

        if load_case:
            lc = self.get_load_case_by_name(load_case)
            if lc:
                for nl in lc.nodal_loads:
                    node = nl.node
                    vec = np.array(nl.direction) * nl.magnitude * display_load_scale
                    mag = np.linalg.norm(vec)
                    if mag > 0:
                        direction = vec / mag
                        p = np.array([node.X, node.Y, node.Z])
                        plotter.add_arrows(
                            p, direction * arrow_scale_for_loads, color="#FFA500", label="Point Load"
                        )
                        mid = p + direction * (arrow_scale_for_loads / 2.0)
                        plotter.add_point_labels(
                            mid,
                            [f"{mag:.2f}"],
                            font_size=14,
                            text_color="#FFA500",
                            always_visible=show_load_labels,
                        )

        if show_nodes:
            nodes = self.get_all_nodes()
            pts = np.array([(n.X, n.Y, n.Z) for n in nodes], dtype=np.float32)
            cloud = pv.PolyData(pts)
            glyph = cloud.glyph(
                geom=pv.Sphere(radius=max(1e-6, structure_size * 0.01)), scale=False, orient=False
            )
            plotter.add_mesh(glyph, color="red", label="Nodes")

        # ---------------------------------------------
        # Supports: arrows + optional square plate for all-fixed translations
        # ---------------------------------------------
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

        plotter.add_legend()

        min_coords, max_coords = self.get_structure_bounds()
        if min_coords and max_coords:
            margin = 0.5
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
        # NEW:
        show_supports: bool = True,
        show_support_labels: bool = True,
        support_size_fraction: float = 0.05,
    ):
        """
        Visualize a load case or combination in 3D using PyVista, with optional
        supports overlay.
        """
        if self.results is None:
            raise ValueError("No analysis results available.")

        if loadcase is not None and loadcombination is not None:
            raise ValueError("Specify either loadcase or loadcombination, not both.")

        # Select the Results object
        if loadcase is not None:
            keys = list(self.results.loadcases.keys())
            if isinstance(loadcase, int):
                try:
                    key = keys[loadcase - 1]
                except IndexError:
                    raise IndexError(f"Loadcase index {loadcase} is out of range.")
            else:
                key = str(loadcase)
                if key not in self.results.loadcases:
                    raise KeyError(f"Loadcase '{key}' not found.")
            chosen = self.results.loadcases[key]
        elif loadcombination is not None:
            keys = list(self.results.loadcombinations.keys())
            if isinstance(loadcombination, int):
                try:
                    key = keys[loadcombination - 1]
                except IndexError:
                    raise IndexError(f"Loadcombination index {loadcombination} is out of range.")
            else:
                key = str(loadcombination)
                if key not in self.results.loadcombinations:
                    raise KeyError(f"Loadcombination '{key}' not found.")
            chosen = self.results.loadcombinations[key]
        else:
            # auto-pick if there is exactly one loadcase and zero combinations
            if len(self.results.loadcases) == 1 and not self.results.loadcombinations:
                chosen = next(iter(self.results.loadcases.values()))
            else:
                raise ValueError("Multiple results available – specify loadcase= or loadcombination=.")

        displacement_nodes = chosen.displacement_nodes

        # -----------------------------
        # Helpers
        # -----------------------------

        def get_local_transform(member):
            lx, ly, lz = member.local_coordinate_system()
            return np.column_stack([lx, ly, lz])

        def interpolate_member(member, d_start, r_start, d_end, r_end):
            L = member.length()
            local_deflections = interpolate_beam_local(0.0, L, d_start, d_end, r_start, r_end, num_points)
            return local_deflections * displacement_scale

        def plot_section(member, d_start_vec, r_start_vec, d_end_vec, r_end_vec, plotter_ref):
            section = getattr(member, "section", None)
            if section is None or getattr(section, "shape_path", None) is None:
                return

            coords_2d, edges = section.shape_path.get_shape_geometry()
            coords_local = np.array([[0.0, y, z] for y, z in coords_2d], dtype=np.float32)
            R = get_local_transform(member)
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
            plotter_ref.add_mesh(orig_extruded, color="steelblue", label=f"Section {section.name}")

            if displacement:
                dls, rls = transform_dofs_global_to_local(d_start_vec, r_start_vec, R)
                dle, rle = transform_dofs_global_to_local(d_end_vec, r_end_vec, R)
                local_def = interpolate_member(member, dls, rls, dle, rle)
                t_vals = np.linspace(0, 1, num_points)
                curve_pts = []
                for i, t in enumerate(t_vals):
                    orig_pt = origin + t * direction
                    defl_local = local_def[i]
                    defl_global = R @ defl_local
                    curve_pts.append(orig_pt + defl_global)
                curve_pts = np.array(curve_pts)
                spline = pv.Spline(curve_pts, num_points * 2)
                deformed = extrude_along_path(section.shape_path, spline.points)
                plotter_ref.add_mesh(deformed, color="red", label=f"Deformed Section {section.name}")

        # -----------------------------
        # Start drawing
        # -----------------------------
        plotter = pv.Plotter()
        plotter.add_axes()

        # scale for support glyphs
        min_coords, max_coords = self.get_structure_bounds()
        if min_coords and max_coords:
            structure_size = np.linalg.norm(np.array(max_coords) - np.array(min_coords))
        else:
            structure_size = 1.0
        support_arrow_scale = max(1e-6, structure_size * support_size_fraction)

        # precompute nodal positions and displacements
        node_pos: Dict[int, np.ndarray] = {}
        node_disp: Dict[int, Tuple[np.ndarray, np.ndarray]] = {}
        for nid_str, nodisp in displacement_nodes.items():
            nid = int(nid_str)
            node = self.get_node_by_pk(nid)
            if node is None:
                continue
            p = np.array([node.X, node.Y, node.Z])
            node_pos[nid] = p
            if displacement and nodisp:
                dgl = np.array([nodisp.dx, nodisp.dy, nodisp.dz])
                rgl = np.array([nodisp.rx, nodisp.ry, nodisp.rz])
            else:
                dgl = np.zeros(3)
                rgl = np.zeros(3)
            node_disp[nid] = (dgl, rgl)

        # sections
        if show_sections:
            for m in self.get_all_members():
                ds, rs = node_disp[m.start_node.id]
                de, re = node_disp[m.end_node.id]
                plot_section(m, ds, rs, de, re, plotter)

        # nodes (original and deformed)
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

        # member center-lines
        for m in self.get_all_members():
            sid = m.start_node.id
            eid = m.end_node.id
            p0 = node_pos[sid]
            p1 = node_pos[eid]
            d0, r0 = node_disp[sid]
            d1, r1 = node_disp[eid]

            R = get_local_transform(m)
            local_def = (
                interpolate_beam_local(
                    0.0,
                    m.length(),
                    *transform_dofs_global_to_local(d0, r0, R),
                    *transform_dofs_global_to_local(d1, r1, R),
                    num_points,
                )
                * displacement_scale
            )

            t_vals = np.linspace(0, 1, num_points)
            orig_curve = np.array([p0 + t * (p1 - p0) for t in t_vals])
            def_curve = np.array([orig_curve[i] + (R @ local_def[i]) for i in range(num_points)])

            plotter.add_lines(orig_curve, color="blue", width=2, label="Original Shape")
            plotter.add_lines(def_curve, color="red", width=2, label="Deformed Shape")

        # supports
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

                    legend_label = None
                    if condition_type not in legend_added_for_type:
                        legend_label = f"Support {axis_name} – {condition_type.title()}"
                        legend_added_for_type.add(condition_type)

                    plotter.add_arrows(
                        node_position,
                        axis_vector * support_arrow_scale,
                        color=color_value,
                        label=legend_label,
                    )

                if show_support_labels:
                    label_text = format_support_label(nodal_support)
                    label_position = node_position + np.array([1.0, 1.0, 1.0]) * (support_arrow_scale * 0.6)
                    plotter.add_point_labels(
                        label_position,
                        [label_text],
                        font_size=12,
                        text_color="black",
                        always_visible=True,
                    )

        plotter.add_legend()
        plotter.show_grid(color="gray")
        plotter.show(title=f'3D Results: "{chosen.name}"')

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
    ):
        """
        Plot all member sets in the model on the specified plane and (optionally)
        overlay nodal supports.

        Parameters:
        - plane: 'xy', 'xz', or 'yz'
        - show_supports: draw a glyph at nodes that have a NodalSupport
        - annotate_supports: print compact text describing support conditions
        - support_marker_size: Matplotlib scatter marker size
        - support_marker_facecolor: face color for the support marker
        - support_marker_edgecolor: edge color for the support marker
        - support_annotation_fontsize: font size for support text labels
        - support_annotation_offset_xy: pixel offset for the label relative to the node
        """

        # -------------------------------
        # Helpers
        # -------------------------------
        def project_xyz_to_plane(x: float, y: float, z: float, plane_name: str) -> tuple[float, float]:
            plane_name = plane_name.lower()
            if plane_name == "xy":
                return x, y
            if plane_name == "xz":
                return x, z
            if plane_name == "yz":
                return y, z
            raise ValueError("plane must be one of 'xy', 'xz', 'yz'")

        # -------------------------------
        # Main plotting
        # -------------------------------
        figure, axes = plt.subplots()

        # Draw all member sets as you already do
        for member_set in self.member_sets:
            member_set.plot(
                plane=plane,
                fig=figure,
                ax=axes,
                set_aspect=False,
                show_title=False,
                show_legend=False,
            )

        # Overlay nodal supports
        if show_supports:
            support_label_added_to_legend = False
            nodes_with_support = [
                node for node in self.get_all_nodes() if getattr(node, "nodal_support", None)
            ]

            # Group nodes by marker so we can call scatter once per marker
            from collections import defaultdict

            marker_groups: dict[str, list[tuple[float, float, object]]] = defaultdict(list)

            for node in nodes_with_support:
                x2d, y2d = project_xyz_to_plane(node.X, node.Y, node.Z, plane)
                marker_symbol = choose_marker(node.nodal_support)
                marker_groups[marker_symbol].append((x2d, y2d, node))

            for marker_symbol, items in marker_groups.items():
                xs = [p[0] for p in items]
                ys = [p[1] for p in items]
                # Add one legend label only once (for the first marker group)
                legend_label = "Nodal Supports" if not support_label_added_to_legend else None
                axes.scatter(
                    xs,
                    ys,
                    s=support_marker_size,
                    marker=marker_symbol,
                    facecolors=support_marker_facecolor,
                    edgecolors=support_marker_edgecolor,
                    linewidths=0.5,
                    zorder=5,
                    label=legend_label,
                )
                support_label_added_to_legend = True

                # Optional annotations with exact conditions
                if annotate_supports:
                    for x2d, y2d, node in items:
                        text = format_support_short(node.nodal_support)
                        axes.annotate(
                            text,
                            (x2d, y2d),
                            textcoords="offset points",
                            xytext=support_annotation_offset_xy,
                            fontsize=support_annotation_fontsize,
                            color="black",
                            zorder=6,
                        )

        axes.set_title("Combined Model Plot")
        figure.tight_layout()
        plt.show()

    def get_model_summary(self):
        """Returns a summary of the model's components: MemberSets, LoadCases, and LoadCombinations."""
        summary = {
            "MemberSets": [member_set.memberset_id for member_set in self.member_sets],  # fixed
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
