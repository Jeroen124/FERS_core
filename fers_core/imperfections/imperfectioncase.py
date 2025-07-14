from ..imperfections.rotationimperfection import RotationImperfection
from ..imperfections.translationimperfection import TranslationImperfection
from ..loads.loadcombination import LoadCombination
from typing import Optional


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

        self.imperfection_case_id = id or ImperfectionCase._imperfection_case_counter
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
            "loadcombinations": [lc.id for lc in self.loadcombinations],
            "rotation_imperfections": [ri.id for ri in self.rotation_imperfections],
            "translation_imperfections": [ti.id for ti in self.translation_imperfections],
        }
