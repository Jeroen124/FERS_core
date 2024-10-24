import re

import matplotlib.pyplot as plt

from FERS_core.imperfections.imperfectioncase import ImperfectionCase
from FERS_core.loads.loadcase import LoadCase
from FERS_core.loads.loadcombination import LoadCombination
from FERS_core.members.member import Member
from FERS_core.members.section import Section
from FERS_core.members.memberhinge import MemberHinge
from FERS_core.members.memberset import MemberSet
from FERS_core.nodes.node import Node
from FERS_core.supports.nodalsupport import NodalSupport


class FERS:
    def __init__(self):
        self.member_sets = []
        self.load_cases = []
        self.load_combinations = []
        self.imperfection_cases = []
        self.analysis_options = None
        self.results = None

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
                    node_mapping[(original_node.pk, i)] = new_node

        for i in range(1, count):
            for original_member_set in original_model.get_all_member_sets():
                new_members = []
                for member in original_member_set.members:
                    new_start_node = node_mapping[(member.start_node.pk, i)]
                    new_end_node = node_mapping[(member.end_node.pk, i)]
                    if member.reference_node is not None:
                        new_reference_node = node_mapping[(member.reference_node.pk, i)]
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
                    L_y=original_member_set.L_y,
                    L_z=original_member_set.L_z,
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
            node_translation_map[original_node.pk] = translated_node

        # Reconstruct member sets with translated nodes
        for original_member_set in model.get_all_member_sets():
            new_members = []
            for member in original_member_set.members:
                new_start_node = node_translation_map[member.start_node.pk]
                new_end_node = node_translation_map[member.end_node.pk]
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

    def get_all_load_cases(self):
        """Return all load cases in the model."""
        return self.load_cases

    def get_all_nodal_loads(self):
        """Return all nodal loads in the model."""
        nodal_loads = []
        for load_case in self.get_all_load_cases():
            nodal_loads.extend(load_case.nodal_loads)
        return nodal_loads

    def get_all_line_loads(self):
        """Return all line loads in the model."""
        line_loads = []
        for load_case in self.get_all_load_cases():
            line_loads.extend(load_case.line_loads)
        return line_loads

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
                if member.pk not in member_ids:
                    members.append(member)
                    member_ids.add(member.pk)

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
                if member.start_node.pk not in node_ids:
                    nodes.append(member.start_node)
                    node_ids.add(member.start_node.pk)

                if member.end_node.pk not in node_ids:
                    nodes.append(member.end_node)
                    node_ids.add(member.end_node.pk)

        return nodes

    def get_node_by_pk(self, pk):
        """Returns a node by its PK."""
        for node in self.get_all_nodes():
            if node.pk == pk:
                return node
        return None

    def get_unique_materials(self):
        """
        Retrieves all unique materials used across all member sets and members.

        Returns:
            List[Material]: A list of unique Material objects used in the model.
        """
        unique_materials = {}  # Use a dictionary to avoid duplicates based on material name

        for member_set in self.member_sets:
            for member in member_set.members:
                # Check if we've already added this material by name
                if member.section.material.name not in unique_materials:
                    # Add the material to the dictionary
                    unique_materials[member.section.material.name] = member.section.material

        # Return the materials as a list
        return list(unique_materials.values())

    def get_unique_situations(self):
        """
        Returns a set of unique conditions used in the model, identified by their names.
        """
        unique_situations = set()
        for load_combination in self.load_combinations:
            if load_combination.situation:
                unique_situations.add(load_combination.situation)
        return unique_situations

    def get_unique_sections(self):
        """
        Returns a set of unique sections used in the model, identified by their names.
        """
        unique_sections = {}  # Use a dictionary to avoid duplicates based on section name

        for member_set in self.member_sets:
            for member in member_set.members:
                # Check if we've already added this section by name
                if member.section.name not in unique_sections:
                    # Add the section to the dictionary
                    unique_sections[member.section.name] = member.section

        # Return the materials as a list
        return list(unique_sections.values())

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

    def get_unique_section_material_combinations(self, rstab_materials):
        """
        Returns a list of unique (section name, material name, material index) tuples used in the model.
        """
        unique_combinations = set()
        material_name_to_index = {material["Name"]: material["index"] for material in rstab_materials}

        for member_set in self.member_sets:
            for member in member_set.members:
                material_name = member.section.material.name
                section_name = member.section.name
                material_index = material_name_to_index.get(material_name, None)

                if material_index is not None:
                    combination = (section_name, material_name, material_index)
                    unique_combinations.add(combination)
                else:
                    # Handle the case where the material name doesn't have a corresponding index
                    print(f"Warning: No RSTAB material index found for material name '{material_name}'.")

        return unique_combinations

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
                        if node.nodal_support.pk not in unique_nodal_supports:
                            unique_nodal_supports[node.pk] = node.nodal_support

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
                        support_no = node.nodal_support.pk
                        if support_no not in support_details:
                            support_details[support_no] = {
                                "support_no": support_no,
                                "node_nos": set(),
                                "displacement_conditions": node.nodal_support.displacement_conditions,
                                "rotation_conditions": node.nodal_support.rotation_conditions,
                            }
                        # Add the node's number to the list of nodes for this NodalSupport
                        support_details[support_no]["node_nos"].add(node.pk)

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
            if load_combination.pk == pk:
                return load_combination
        return None

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
            "MemberSets": [member_set.pk for member_set in self.member_sets],
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
        L_y=None,
        L_z=None,
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

        member_set = MemberSet(members=members, classification=classification, L_y=L_y, L_z=L_z)
        return member_set

    @staticmethod
    def combine_member_sets(*member_sets):
        combined_members = []
        for member_set in member_sets:
            # Assuming .members is a list of Member objects in each MemberSet
            combined_members.extend(member_set.members)

        combined_member_set = MemberSet(members=combined_members)
        return combined_member_set
