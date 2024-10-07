class Material:
    def __init__(self, id: int, name: str, E_mod: float, G_mod: float, density: float, yield_stress: float):
        self.id = id
        self.name = name
        self.E_mod = E_mod
        self.G_mod = G_mod
        self.density = density
        self.yield_stress = yield_stress
