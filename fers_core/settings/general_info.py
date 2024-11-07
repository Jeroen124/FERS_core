class GeneralInfo:
    def __init__(self, project_name: str = "Unnamed Project", author: str = "Unknown", version: str = "1.0"):
        self.general_info = {"project_name": project_name, "author": author, "version": version}

    def to_dict(self) -> dict:
        return {
            "project_name": self.general_info["project_name"],
            "author": self.general_info["author"],
            "version": self.general_info["version"],
        }
