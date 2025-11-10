from typing import Optional

from fers_core.settings.units_settings import UnitSettings
from ..settings.anlysis_options import AnalysisOptions
from ..settings.general_info import GeneralInfo


class Settings:
    _settings_counter = 1

    def __init__(
        self,
        analysis_options: Optional[AnalysisOptions] = None,
        general_info: Optional[GeneralInfo] = None,
        unit_settings: Optional[UnitSettings] = None,
        id: Optional[int] = None,
    ):
        self.settings_id = id or Settings._settings_counter
        if id is None:
            Settings._settings_counter += 1
        self.analysis_options = analysis_options if analysis_options else AnalysisOptions()
        self.general_info = general_info if general_info else GeneralInfo()
        self.unit_settings = unit_settings if unit_settings else UnitSettings()

    @classmethod
    def reset_counter(cls):
        cls._settings_counter = 1

    def to_dict(self):
        return {
            "id": self.settings_id,
            "analysis_options": self.analysis_options.to_dict(),
            "unit_settings": self.unit_settings.to_dict(),
            "general_info": self.general_info.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Settings":
        analysis_options_data = data.get("analysis_options") or {}
        general_info_data = data.get("general_info") or {}
        unit_settings_data = data.get("unit_settings") or {}

        # Assuming these have from_dict; if not, construct directly from kwargs
        analysis_options = AnalysisOptions.from_dict(analysis_options_data)
        general_info = GeneralInfo.from_dict(general_info_data)
        unit_settings = UnitSettings.from_dict(unit_settings_data)
        return cls(
            analysis_options=analysis_options,
            general_info=general_info,
            unit_settings=unit_settings,
            id=data.get("id"),
        )
