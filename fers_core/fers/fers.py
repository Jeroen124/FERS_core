import re
from typing import Any, Dict, Optional, Tuple, Union
import fers_calculations
import ujson

import numpy as np
import matplotlib.pyplot as plt
import pyvista as pv

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
            validated = ResultsBundleSchema(**results_dictionary)
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
            validated = ResultsBundleSchema(**results_dictionary)
            self.resultsbundle = ResultsBundle.from_pydantic(validated)
        except Exception as e:
            raise ValueError(f"Failed to parse or validate results: {e}")

    def to_dict(self, include_results: bool = True) -> Dict[str, Any]:
        data: Dict[str, Any] = {
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

    def show_results_2d(
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

        # -----------------------------
        # Select which result set to show
        # -----------------------------
        if loadcase is not None:
            loadcase_keys = list(self.resultsbundle.loadcases.keys())
            if isinstance(loadcase, int):
                if loadcase < 1 or loadcase > len(loadcase_keys):
                    raise IndexError(f"Loadcase index {loadcase} is out of range.")
                selected_key = loadcase_keys[loadcase - 1]
            else:
                selected_key = str(loadcase)
                if selected_key not in self.resultsbundle.loadcases:
                    raise KeyError(f"Loadcase '{selected_key}' not found.")
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
                    raise KeyError(f"Loadcombination '{selected_key}' not found.")
            chosen_results = self.resultsbundle.loadcombinations[selected_key]
            chosen_title = chosen_results.name if hasattr(chosen_results, "name") else str(selected_key)
        else:
            if len(self.resultsbundle.loadcases) == 1 and not self.resultsbundle.loadcombinations:
                chosen_results = next(iter(self.resultsbundle.loadcases.values()))
                chosen_title = chosen_results.name if hasattr(chosen_results, "name") else "Loadcase"
            else:
                raise ValueError("Multiple results available. Specify 'loadcase' or 'loadcombination'.")

        # -----------------------------
        # Plane helpers
        # -----------------------------
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

        # -----------------------------
        # Result field helpers (aligns with your 3D method)
        # -----------------------------
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

        # -----------------------------
        # Gather node displacements (for deformed centerlines)
        # -----------------------------
        need_displacements = show_deformations or (plot_local_bending_moment is not None)
        node_displacements: Dict[int, Tuple[np.ndarray, np.ndarray]] = {}
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

        # -----------------------------
        # Prepare plotting
        # -----------------------------
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

        # -----------------------------
        # Draw original and deformed centerlines
        # -----------------------------
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

        # -----------------------------
        # Optional: draw nodes
        # -----------------------------
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

        # -----------------------------
        # Optional: draw supports in 2D (very compact, plane-aware)
        # -----------------------------
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

        # -----------------------------
        # Optional: local bending moment diagrams in the 2D plane
        # -----------------------------
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

        # -----------------------------
        # Final formatting
        # -----------------------------
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
        show_supports: bool = True,
        show_support_labels: bool = True,
        support_size_fraction: float = 0.05,
        plot_bending_moment: Optional[str] = None,  # One of: None, "M_x", "M_y", "M_z"
        moment_scale: Optional[float] = None,  # If None: auto-scale relative to model size
        moment_num_points: int = 41,  # Samples along each member for the diagram
        color_members_by_peak_moment: bool = False,  # Color member centerlines by peak |M|
        show_moment_colorbar: bool = True,  # Show colorbar for moment diagram
        diagram_line_width_pixels: int = 6,  # Used for 'line' moment_style
        diagram_on_deformed_centerline: bool = True,  # Draw diagram offset from deformed centerline
        moment_style: str = "tube",
    ):
        """
        Visualize a load case or combination in 3D using PyVista.

        Default (plot_bending_moment=None): original + deformed shapes.
        If plot_bending_moment in {"M_x","M_y","M_z"}:
        - moment_style="tube": draw a scaled 3D diagram as tubes, offset along the local axis
        - moment_style="line": draw unscaled centerlines, colored by the moment along the length
        """
        if self.resultsbundle is None:
            raise ValueError("No analysis results available.")
        if loadcase is not None and loadcombination is not None:
            raise ValueError("Specify either loadcase or loadcombination, not both.")

        # -----------------------------
        # Pick results
        # -----------------------------
        if loadcase is not None:
            keys = list(self.resultsbundle.loadcases.keys())
            if isinstance(loadcase, int):
                try:
                    key = keys[loadcase - 1]
                except IndexError:
                    raise IndexError(f"Loadcase index {loadcase} is out of range.")
            else:
                key = str(loadcase)
                if key not in self.resultsbundle.loadcases:
                    raise KeyError(f"Loadcase '{key}' not found.")
            chosen = self.resultsbundle.loadcases[key]
        elif loadcombination is not None:
            keys = list(self.resultsbundle.loadcombinations.keys())
            if isinstance(loadcombination, int):
                try:
                    key = keys[loadcombination - 1]
                except IndexError:
                    raise IndexError(f"Loadcombination index {loadcombination} is out of range.")
            else:
                key = str(loadcombination)
                if key not in self.resultsbundle.loadcombinations:
                    raise KeyError(f"Loadcombination '{key}' not found.")
            chosen = self.resultsbundle.loadcombinations[key]
        else:
            if len(self.resultsbundle.loadcases) == 1 and not self.resultsbundle.loadcombinations:
                chosen = next(iter(self.resultsbundle.loadcases.values()))
            else:
                raise ValueError("Multiple results available – specify loadcase= or loadcombination=.")

        # -----------------------------
        # Plotter + global scales
        # -----------------------------
        plotter = pv.Plotter()
        plotter.add_axes()

        min_coordinates, max_coordinates = self.get_structure_bounds()
        if min_coordinates and max_coordinates:
            structure_size = np.linalg.norm(np.array(max_coordinates) - np.array(min_coordinates))
        else:
            structure_size = 1.0
        support_arrow_scale = max(1e-6, structure_size * support_size_fraction)

        # -----------------------------
        # Displacements (for deformed centerline)
        # -----------------------------
        need_displacements = (plot_bending_moment is None and displacement) or (
            plot_bending_moment is not None and diagram_on_deformed_centerline
        )
        node_displacements: Dict[int, Tuple[np.ndarray, np.ndarray]] = {}
        if need_displacements:
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

        # -----------------------------
        # Helpers for moment plotting
        # -----------------------------
        def _normalize_key(s: str) -> str:
            return str(s).lower().replace("_", "")

        def _get_comp(obj, name: str):
            """
            Robustly get a component (attribute or dict item), tolerating 'M_z', 'Mz', 'mz', 'm_z', etc.
            """
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
            # attribute access
            for c in candidates:
                if hasattr(obj, c):
                    return getattr(obj, c)
            # dict-like
            if isinstance(obj, dict):
                for c in candidates:
                    if c in obj:
                        return obj[c]
                # try normalized key match
                for k, v in obj.items():
                    if _normalize_key(k) == _normalize_key(name):
                        return v
            return None

        def _offset_axis(member: Member, component_name: str) -> np.ndarray:
            lx, ly, lz = member.local_coordinate_system()
            lower = component_name.lower()
            if lower in ("m_y", "my"):
                return np.asarray(ly, dtype=float)
            if lower in ("m_z", "mz"):
                return np.asarray(lz, dtype=float)
            if lower in ("m_x", "mx"):
                return np.asarray(lx, dtype=float)
            raise ValueError("plot_bending_moment must be one of 'M_x', 'M_y', 'M_z'.")

        def _resample(num: int, s: np.ndarray, y: np.ndarray) -> np.ndarray:
            s_target = np.linspace(0.0, 1.0, num=num)
            return np.interp(s_target, s, y)

        # Read per-member curve if present (various layouts)
        def _fetch_member_line_curve(member_id: int) -> Optional[Tuple[np.ndarray, np.ndarray]]:
            # Known containers with {s: [...], My/Mz/Mx: [...]}
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
                        m_vals = _get_comp(record, plot_bending_moment)
                        if s_vals is not None and m_vals is not None:
                            s_vals = np.asarray(s_vals, dtype=float)
                            m_vals = np.asarray(m_vals, dtype=float)
                            if s_vals.size > 1 and s_vals.size == m_vals.size:
                                return s_vals, m_vals

            # Nested object style: chosen.members["id"].internal_forces.s, .My/.Mz/.Mx
            members_map = getattr(chosen, "members", None)
            if members_map and str(member_id) in members_map:
                member_obj = members_map[str(member_id)]
                for nested_name in ["internal_forces", "line_forces"]:
                    nested = getattr(member_obj, nested_name, None)
                    if nested is not None:
                        s_vals = _get_comp(nested, "s")
                        m_vals = _get_comp(nested, plot_bending_moment)
                        if s_vals is not None and m_vals is not None:
                            s_vals = np.asarray(s_vals, dtype=float)
                            m_vals = np.asarray(m_vals, dtype=float)
                            if s_vals.size > 1 and s_vals.size == m_vals.size:
                                return s_vals, m_vals
            return None

        # NEW: read end forces from member_results (your data layout)
        def _fetch_member_end_forces(member_id: int) -> Optional[Tuple[np.ndarray, np.ndarray]]:
            """
            Build a linear diagram from element end forces when only end forces are available.
            Supports:
            chosen.member_results[str(id)].start_node_forces.<comp>
            chosen.member_results[str(id)].end_node_forces.<comp>
            and similar dictionaries.
            """
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
                start_val = _get_comp(start_forces, plot_bending_moment)
                end_val = _get_comp(end_forces, plot_bending_moment)
                if start_val is not None and end_val is not None:
                    s_vals = np.array([0.0, 1.0], dtype=float)
                    m_vals = np.array([float(start_val), float(end_val)], dtype=float)
                    return s_vals, m_vals

            # Other possible containers used by different pipelines
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
                    # try nested dicts or flat keys Mz_i / Mz_j etc.
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
                    start_val = _get_comp(start, plot_bending_moment)
                    end_val = _get_comp(end, plot_bending_moment)
                    if start_val is None and isinstance(rec, dict):
                        # flat variants
                        for k, v in rec.items():
                            if _normalize_key(k).startswith(
                                _normalize_key(plot_bending_moment)
                            ) and _normalize_key(k).endswith("i"):
                                start_val = float(v)
                            if _normalize_key(k).startswith(
                                _normalize_key(plot_bending_moment)
                            ) and _normalize_key(k).endswith("j"):
                                end_val = float(v)
                    if start_val is not None and end_val is not None:
                        s_vals = np.array([0.0, 1.0], dtype=float)
                        m_vals = np.array([float(start_val), float(end_val)], dtype=float)
                        return s_vals, m_vals
            return None

        # Last-resort single-span cantilever fallback using reactions
        def _fallback_single_cantilever(member: Member) -> Optional[Tuple[np.ndarray, np.ndarray]]:
            if len(self.get_all_members()) != 1:
                return None
            start_is_supported = getattr(member.start_node, "nodal_support", None) is not None
            end_is_supported = getattr(member.end_node, "nodal_support", None) is not None
            if not (start_is_supported ^ end_is_supported):
                return None
            reactions = getattr(chosen, "reaction_nodes", {})
            if not reactions:
                return None
            supported_node_id = member.start_node.id if start_is_supported else member.end_node.id
            rec = reactions.get(str(supported_node_id))
            if not rec or getattr(rec, "nodal_forces", None) is None:
                return None
            val = _get_comp(rec.nodal_forces, plot_bending_moment)
            if not isinstance(val, (int, float)):
                return None
            if start_is_supported:
                s_vals = np.array([0.0, 1.0], dtype=float)
                m_vals = np.array([float(val), 0.0], dtype=float)
            else:
                s_vals = np.array([0.0, 1.0], dtype=float)
                m_vals = np.array([0.0, float(val)], dtype=float)
            return s_vals, m_vals

        # ======================================================================
        # BRANCH A: Deformed/original shapes (no moment diagram)
        # ======================================================================
        if plot_bending_moment is None:
            centerline_samples = num_points
            extrusion_samples = max(num_points * 2, 2 * num_points + 1)

            labeled_lines = False
            labeled_def_section = False
            labeled_org_section = False

            for member in self.get_all_members():
                d0_gl, r0_gl = node_displacements.get(member.start_node.id, (np.zeros(3), np.zeros(3)))
                d1_gl, r1_gl = node_displacements.get(member.end_node.id, (np.zeros(3), np.zeros(3)))

                original_curve, deformed_curve = centerline_path_points(
                    member, d0_gl, r0_gl, d1_gl, r1_gl, centerline_samples, displacement_scale
                )

                deformed_path_points = np.ascontiguousarray(
                    pv.Spline(deformed_curve, extrusion_samples).points, dtype=float
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
                deformed = []
                for node in self.get_all_nodes():
                    nid = node.id
                    o = np.array([node.X, node.Y, node.Z], dtype=float)
                    dgl, _ = node_displacements.get(nid, (np.zeros(3), np.zeros(3)))
                    originals.append(o)
                    deformed.append(o + dgl * displacement_scale)

                originals = np.array(originals, dtype=float)
                deformed = np.array(deformed, dtype=float)

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
                        label_position = node_position + np.array([1.0, 1.0, 1.0]) * (
                            support_arrow_scale * 0.6
                        )
                        plotter.add_point_labels(
                            label_position,
                            [label_text],
                            font_size=12,
                            text_color="black",
                            always_visible=True,
                        )

            plotter.add_legend()
            plotter.show_grid(color="gray")
            plotter.view_isometric()
            plotter.show(title=f'3D Results: "{chosen.name}"')
            return

        # ======================================================================
        # BRANCH B: Bending-moment diagram as tubes
        # ======================================================================
        diagram_polys: list[pv.PolyData] = []
        diagram_vals: list[np.ndarray] = []
        offset_axes: list[np.ndarray] = []
        peak_abs_by_member: Dict[int, float] = {}

        for member in self.get_all_members():
            curve = _fetch_member_line_curve(member.id)
            if curve is None:
                curve = _fetch_member_end_forces(member.id)
            if curve is None:
                curve = _fallback_single_cantilever(member)
            if curve is None:
                continue

            s_raw, m_raw = curve
            m_resampled = _resample(moment_num_points, np.asarray(s_raw, float), np.asarray(m_raw, float))

            # Choose the reference path (deformed or straight)
            if diagram_on_deformed_centerline:
                d0_gl, r0_gl = node_displacements.get(member.start_node.id, (np.zeros(3), np.zeros(3)))
                d1_gl, r1_gl = node_displacements.get(member.end_node.id, (np.zeros(3), np.zeros(3)))
                _, def_curve = centerline_path_points(
                    member, d0_gl, r0_gl, d1_gl, r1_gl, moment_num_points, displacement_scale
                )
                path_points = np.ascontiguousarray(
                    pv.Spline(def_curve, moment_num_points).points, dtype=float
                )
                path_points[0] = def_curve[0]
                path_points[-1] = def_curve[-1]
            else:
                p0 = np.array([member.start_node.X, member.start_node.Y, member.start_node.Z], dtype=float)
                p1 = np.array([member.end_node.X, member.end_node.Y, member.end_node.Z], dtype=float)
                t = np.linspace(0.0, 1.0, moment_num_points)[:, None]
                path_points = p0[None, :] * (1.0 - t) + p1[None, :] * t

            axis = _offset_axis(member, plot_bending_moment)

            poly = pv.PolyData(path_points.copy())
            poly.lines = np.hstack(
                [np.array([moment_num_points], dtype=np.int32), np.arange(moment_num_points, dtype=np.int32)]
            )
            diagram_polys.append(poly)
            diagram_vals.append(m_resampled)
            offset_axes.append(axis)
            peak_abs_by_member[member.id] = float(np.max(np.abs(m_resampled)))

        if not diagram_polys:
            # Draw members (so the window isn't empty) and return
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
            plotter.add_legend()
            plotter.show_grid(color="gray")
            plotter.view_isometric()
            plotter.show(title=f'Bending Moment Diagram: {plot_bending_moment} – "{chosen.name}"')
            return

        # Auto-scale
        global_abs_max = float(np.max([np.max(np.abs(v)) for v in diagram_vals])) or 1.0
        effective_moment_scale = (
            moment_scale
            if (moment_scale is not None and moment_scale > 0.0)
            else (0.06 * structure_size / global_abs_max)
        )

        # Apply offsets and draw as tubes (guaranteed visible)
        # color_limits = (-global_abs_max, global_abs_max)

        if moment_style.lower() == "tube":
            # Scaled graph as tubes (your existing behavior)
            # tube_radius = max(1e-6, 0.0075 * structure_size)
            for polydata, values, offset_axis in zip(diagram_polys, diagram_vals, offset_axes):
                displaced_points = (
                    polydata.points + (effective_moment_scale * values[:, None]) * offset_axis[None, :]
                )
                polydata.points = displaced_points
                polydata["moment"] = values.astype(float)
                # tube = polydata.tube(radius=tube_radius)

        elif moment_style.lower() == "line":
            # Unscaled centerline colored by moment (no geometric offset)
            for polydata, values in zip(diagram_polys, diagram_vals):
                polydata["moment"] = values.astype(float)

        else:
            raise ValueError("moment_style must be 'tube' or 'line'")

        # Member centerlines (optional coloring by peak |M|)
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
                plotter.add_scalar_bar(title=f"Peak |{plot_bending_moment}| per member")
            else:
                plotter.add_mesh(lines_poly, color="blue", line_width=2.0, label="Members")

        # Nodes
        if show_nodes:
            node_positions = np.array([(n.X, n.Y, n.Z) for n in self.get_all_nodes()], dtype=np.float32)
            cloud = pv.PolyData(node_positions)
            glyph = cloud.glyph(
                geom=pv.Sphere(radius=max(1e-6, structure_size * 0.01)), scale=False, orient=False
            )
            plotter.add_mesh(glyph, color="black", label="Nodes")

        # Supports
        if show_supports:
            legend_added_for_type: set[str] = set()
            axis_unit_vectors = {
                "X": np.array([1.0, 0.0, 0.0]),
                "Y": np.array([0.0, 1.0, 0.0]),
                "Z": np.array([0.0, 0.0, 1.0]),
            }
            for node in self.get_all_nodes():
                support = getattr(node, "nodal_support", None)
                if not support:
                    continue
                p = np.array([node.X, node.Y, node.Z], dtype=float)
                for axis_name, axis_vector in axis_unit_vectors.items():
                    condition_type = get_condition_type(support.displacement_conditions.get(axis_name))
                    color_value = color_for_condition_type(condition_type)
                    label = None
                    if condition_type not in legend_added_for_type:
                        label = f"Support {axis_name} – {condition_type.title()}"
                        legend_added_for_type.add(condition_type)
                    plotter.add_arrows(p, axis_vector * support_arrow_scale, color=color_value, label=label)

                if show_support_labels:
                    text = format_support_label(support)
                    label_pos = p + np.array([1.0, 1.0, 1.0]) * (support_arrow_scale * 0.6)
                    plotter.add_point_labels(
                        label_pos, [text], font_size=12, text_color="black", always_visible=True
                    )

        plotter.add_legend()
        plotter.show_grid(color="gray")
        plotter.view_isometric()
        plotter.show(title=f'Bending Moment Diagram: {plot_bending_moment} – "{chosen.name}"')

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
