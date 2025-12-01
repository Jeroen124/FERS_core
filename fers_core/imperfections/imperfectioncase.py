from ..imperfections.rotationimperfection import RotationImperfection
from ..imperfections.translationimperfection import TranslationImperfection
from ..loads.loadcombination import LoadCombination
from typing import Any, Iterable, Optional


class ImperfectionCase:
    _imperfection_case_counter = 1

    def __init__(
        self,
        loadcombinations: list[LoadCombination],
        imperfection_case_id: Optional[int] = None,
        rotation_imperfections: Optional[list[RotationImperfection]] = None,
        translation_imperfections: Optional[list[TranslationImperfection]] = None,
    ):
        """
        Initialize a new ImperfectionCase instance.

        Args:
            loadcombinations (list[LoadCombination]):   List of LoadCombination instances associated with
                                                        this ImperfectionCase. Represents the combinations
                                                        of loads that are considered in the analysis.
            imperfection_case_id (int, optional):       Unique identifier for the ImperfectionCase instance.
                                                        If not provided, an auto-incremented value based
                                                        on the class counter is used.
            rotation_imperfections (list[RotationImperfection], optional):  List of RotationImperfection
                                                                            instances associated with this
                                                                            ImperfectionCase.
            translation_imperfections (list[TranslationImperfection], optional):
                                                                            List of TranslationImper.
                                                                            instances associated with
                                                                            this ImperfectionCase.
        """

        self.imperfection_case_id = imperfection_case_id or ImperfectionCase._imperfection_case_counter
        if imperfection_case_id is None:
            ImperfectionCase._imperfection_case_counter += 1
        self.loadcombinations = loadcombinations
        self.rotation_imperfections = rotation_imperfections if rotation_imperfections is not None else []
        self.translation_imperfections = (
            translation_imperfections if translation_imperfections is not None else []
        )

    @classmethod
    def reset_counter(cls):
        cls._imperfection_case_counter = 1

    def add_rotation_imperfection(self, imperfection):
        self.rotation_imperfections.append(imperfection)

    def add_translation_imperfection(self, imperfection):
        self.translation_imperfections.append(imperfection)

    def to_dict(self):
        return {
            "imperfection_case_id": self.imperfection_case_id,
            "load_combinations": [lc.id for lc in self.loadcombinations],
            "rotation_imperfections": [ri.to_dict() for ri in self.rotation_imperfections],
            "translation_imperfections": [ti.to_dict() for ti in self.translation_imperfections],
        }

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        *,
        load_combinations: Iterable[LoadCombination],
    ) -> "ImperfectionCase":
        """
        Expected schema (matching to_dict):
        {
            "imperfection_case_id": int,
            "load_combinations": [lc_id, ...],
            "rotation_imperfections": [ {...}, ... ],
            "translation_imperfections": [ {...}, ... ]
        }
        """
        by_id = {lc.id: lc for lc in load_combinations}
        loadcomb_ids = data.get("load_combinations", []) or []
        resolved_lcs: list[LoadCombination] = []

        for ref in loadcomb_ids:
            lc = None
            if isinstance(ref, int):
                lc = by_id.get(ref)
            elif isinstance(ref, str) and ref.isdigit():
                lc = by_id.get(int(ref))
            else:
                # allow fallback by name
                for cand in load_combinations:
                    if cand.name == str(ref):
                        lc = cand
                        break
            if lc is None:
                raise KeyError(
                    f"ImperfectionCase.from_dict: cannot resolve load combination {ref!r} "
                    f"for imperfection case {data.get('imperfection_case_id')!r}"
                )
            resolved_lcs.append(lc)

        # Rotation imperfections
        rotation_imperfections: list[RotationImperfection] = []
        for ri_data in data.get("rotation_imperfections", []) or []:
            if isinstance(ri_data, RotationImperfection):
                rotation_imperfections.append(ri_data)
            elif hasattr(RotationImperfection, "from_dict") and isinstance(ri_data, dict):
                rotation_imperfections.append(RotationImperfection.from_dict(ri_data))
            else:
                # last resort: ignore or raise; here we raise so bad input is visible
                raise TypeError("Invalid rotation_imperfection entry in ImperfectionCase.from_dict")

        # Translation imperfections
        translation_imperfections: list[TranslationImperfection] = []
        for ti_data in data.get("translation_imperfections", []) or []:
            if isinstance(ti_data, TranslationImperfection):
                translation_imperfections.append(ti_data)
            elif hasattr(TranslationImperfection, "from_dict") and isinstance(ti_data, dict):
                translation_imperfections.append(TranslationImperfection.from_dict(ti_data))
            else:
                raise TypeError("Invalid translation_imperfection entry in ImperfectionCase.from_dict")

        return cls(
            loadcombinations=resolved_lcs,
            imperfection_case_id=data.get("imperfection_case_id") or data.get("id"),
            rotation_imperfections=rotation_imperfections,
            translation_imperfections=translation_imperfections,
        )
