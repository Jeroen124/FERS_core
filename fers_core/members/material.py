from typing import Optional


class Material:
    _material_counter = 1

    def __init__(
        self,
        name: str,
        E_mod: float,
        G_mod: float,
        density: float,
        yield_stress: float,
        material_id: Optional[int] = None,
    ):
        self.id = material_id or Material._material_counter
        if material_id is None:
            Material._material_counter += 1
        self.name = name
        self.E_mod = E_mod
        self.G_mod = G_mod
        self.density = density
        self.yield_stress = yield_stress

    @classmethod
    def reset_counter(cls):
        cls._material_counter = 1
