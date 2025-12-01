class UnitSettings:
    def __init__(
        self,
        system: str = "metric",
        length_unit: str = "m",
        force_unit: str = "N",
        density_unit: str = "kg/m3",
        weight_unit: str = "kg",
        pressure_unit: str = "Pa",
        temperature_unit: str = "celsius",
    ):
        self.system = system
        self.length_unit = length_unit
        self.force_unit = force_unit
        self.density_unit = density_unit
        self.weight_unit = weight_unit
        self.pressure_unit = pressure_unit
        self.temperature_unit = temperature_unit

    def to_dict(self):
        return {
            "system": self.system,
            "lengthUnit": self.length_unit,
            "forceUnit": self.force_unit,
            "densityUnit": self.density_unit,
            "weightUnit": self.weight_unit,
            "pressureUnit": self.pressure_unit,
            "temperatureUnit": self.temperature_unit,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "UnitSettings":
        """
        Inverse of to_dict.

        Accepts both:
        - camelCase keys used in to_dict
        - or snake_case alternatives, to be forgiving.
        """
        if data is None:
            return cls()

        def get(*keys, default=None):
            for key in keys:
                if key in data:
                    return data[key]
            return default

        return cls(
            system=get("system", default="metric"),
            length_unit=get("lengthUnit", "length_unit", default="m"),
            force_unit=get("forceUnit", "force_unit", default="N"),
            density_unit=get("densityUnit", "density_unit", default="kg/m3"),
            weight_unit=get("weightUnit", "weight_unit", default="kg"),
            pressure_unit=get("pressureUnit", "pressure_unit", default="MPa"),
            temperature_unit=get("temperatureUnit", "temperature_unit", default="celsius"),
        )
