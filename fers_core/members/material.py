from typing import Optional


class Material:
    _material_counter = 1

    def __init__(
        self,
        name: str,
        e_mod: float,
        g_mod: float,
        density: float,
        yield_stress: float,
        id: Optional[int] = None,
    ):
        self.id = id or Material._material_counter
        if id is None:
            Material._material_counter += 1
        self.name = name
        self.e_mod = e_mod
        self.g_mod = g_mod
        self.density = density
        self.yield_stress = yield_stress

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "e_mod": self.e_mod,
            "g_mod": self.g_mod,
            "density": self.density,
            "yield_stress": self.yield_stress,
        }

    @classmethod
    def reset_counter(cls):
        cls._material_counter = 1
