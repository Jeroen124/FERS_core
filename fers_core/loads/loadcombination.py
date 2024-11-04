from .loadcase import LoadCase


class LoadCombination:
    _load_combination_counter = 1
    _all_load_combinations = []

    def __init__(
        self,
        name: str = "Load Combination",
        load_cases_factors: dict = None,
        situation: str = None,
        check: str = "ALL",
    ):
        """
        Initialize a LoadCombination instance with a specified name, factors for load cases, and other.

        Args:
            name (str): The name of the Load Combination.
            load_cases_factors (dict): A dictionary mapping LoadCase instances to their corresponding factors (float).
            situation (str, optional): A description of the situation for this load combination.
            check (str, optional): A parameter to determine the type of checks to perform, defaulting to 'ALL'.
        """  # noqa: E501
        self.id = LoadCombination._load_combination_counter
        LoadCombination._load_combination_counter += 1
        self.name = name
        self.load_cases_factors = load_cases_factors or {}
        self.situation = situation
        self.check = check
        LoadCombination._all_load_combinations.append(self)

    @classmethod
    def reset_counter(cls):
        cls._load_combination_counter = 1

    @classmethod
    def names(cls):
        return cls._all_load_cases.name

    @classmethod
    def get_all_load_combinations(cls):
        return cls._all_load_combinations

    def add_load_case(self, load_case: LoadCase, factor: float):
        self.load_cases_factors[load_case] = factor

    def rstab_combination_items(self):
        combination_items = []

        for load_case_key, factor in self.load_cases_factors.items():
            rstab_load_case_number = load_case_key
            combination_items.append([factor, rstab_load_case_number, 0, False])

        return combination_items

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "load_cases_factors": {lc.id: factor for lc, factor in self.load_cases_factors.items()},
            "situation": self.situation,
            "check": self.check,
        }
