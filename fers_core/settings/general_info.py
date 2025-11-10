class GeneralInfo:
    def __init__(self, project_name: str = "Unnamed Project", author: str = "Unknown", version: str = "1.0"):
        self.general_info = {"project_name": project_name, "author": author, "version": version}

    def to_dict(self) -> dict:
        return {
            "project_name": self.general_info["project_name"],
            "author": self.general_info["author"],
            "version": self.general_info["version"],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GeneralInfo":
        if data is None:
            return cls()
        return cls(
            project_name=data.get("project_name", "Unnamed Project"),
            author=data.get("author", "Unknown"),
            version=data.get("version", "1.0"),
        )
