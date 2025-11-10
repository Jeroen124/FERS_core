from typing import Any, Iterable
from fers_core.loads.enums import LimitState
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
        limit_state: LimitState | None = None,
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
        self.limit_state = limit_state
        LoadCombination._all_load_combinations.append(self)

    @classmethod
    def reset_counter(cls):
        cls._load_combination_counter = 1

    @classmethod
    def names(cls):
        return [lc.name for lc in cls._all_load_combinations]

    @classmethod
    def get_all_load_combinations(cls):
        return cls._all_load_combinations

    @staticmethod
    def _index_load_cases(load_cases: Iterable[LoadCase]) -> tuple[dict[int, LoadCase], dict[str, LoadCase]]:
        by_id: dict[int, LoadCase] = {}
        by_name: dict[str, LoadCase] = {}
        for lc in load_cases:
            by_id[int(lc.id)] = lc
            if lc.name is not None:
                by_name[str(lc.name)] = lc
        return by_id, by_name

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
            "limit_state": self.limit_state,
        }

    @staticmethod
    def _parse_limit_state(raw: Any) -> LimitState | None:
        if raw is None or raw == "":
            return None
        if isinstance(raw, LimitState):
            return raw

        # Accept strings like "ULS", "SLS", etc. or their .value
        if isinstance(raw, str):
            txt = raw.strip()
            # try name
            for ls in LimitState:
                if txt.upper() == ls.name.upper():
                    return ls
            # try value match if enum values are strings
            for ls in LimitState:
                if str(ls.value) == txt:
                    return ls

        # Accept numeric values if your LimitState uses them
        if isinstance(raw, (int, float)):
            for ls in LimitState:
                if ls.value == raw:
                    return ls

        raise ValueError(f"Unrecognized limit_state value in LoadCombination.from_dict: {raw!r}")

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        *,
        load_cases: Iterable[LoadCase],
    ) -> "LoadCombination":
        """
        Rebuild a LoadCombination from its dict representation.

        Expected schema (matching to_dict):
        {
            "id": int,
            "name": str,
            "load_cases_factors": { <load_case_id or name>: factor, ... },
            "situation": str | None,
            "check": str,
            "limit_state": str | int | LimitState | None
        }
        """
        by_id, by_name = cls._index_load_cases(load_cases)

        raw_factors = data.get("load_cases_factors", {}) or {}
        load_cases_factors: dict[LoadCase, float] = {}

        for key, factor in raw_factors.items():
            lc: LoadCase | None = None

            # Try as id
            if isinstance(key, int):
                lc = by_id.get(key)
            elif isinstance(key, str) and key.isdigit():
                lc = by_id.get(int(key))

            # Fallback: treat as name
            if lc is None:
                lc = by_name.get(str(key))

            if lc is None:
                raise KeyError(
                    f"LoadCombination.from_dict: cannot resolve load case reference {key!r} "
                    f"for combination {data.get('name')!r}"
                )

            load_cases_factors[lc] = float(factor)

        limit_state = None
        if "limit_state" in data:
            limit_state = cls._parse_limit_state(data["limit_state"])

        obj = cls(
            id=data.get("id"),
            name=data.get("name", f"Load Combination {data.get('id', '')}"),
            load_cases_factors=load_cases_factors,
            situation=data.get("situation"),
            check=data.get("check", "ALL"),
            limit_state=limit_state,
        )
        return obj
