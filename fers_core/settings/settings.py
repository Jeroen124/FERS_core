from typing import Optional
from FERS_core.settings.anlysis_options import AnalysisOptions
from FERS_core.settings.general_info import GeneralInfo


class Settings:
    _settings_counter = 1

    def __init__(
        self,
        analysis_option: Optional[AnalysisOptions] = None,
        general_info: Optional[GeneralInfo] = None,
        id: Optional[int] = None,
    ):
        self.settings_id = id or Settings._settings_counter
        if id is None:
            Settings._settings_counter += 1
        self.analysis_option = analysis_option if analysis_option else AnalysisOptions()
        self.general_info = general_info if general_info else GeneralInfo()

    @classmethod
    def reset_counter(cls):
        cls._settings_counter = 1

    def to_dict(self):
        return {
            "id": self.settings_id,
            "analysis_option": self.analysis_option.to_dict(),
            "general_info": self.general_info.to_dict(),
        }
