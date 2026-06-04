from typing import Optional


class OrthotropicPlateMaterial:
    """Optional orthotropic plate properties in the plate's local axes."""

    def __init__(
        self,
        e_x: float,
        e_y: float,
        g_xy: float,
        nu_xy: float,
        g_xz: Optional[float] = None,
        g_yz: Optional[float] = None,
    ):
        self.e_x = e_x
        self.e_y = e_y
        self.g_xy = g_xy
        self.nu_xy = nu_xy
        self.g_xz = g_xz
        self.g_yz = g_yz

    def to_dict(self) -> dict:
        data = {
            "e_x": self.e_x,
            "e_y": self.e_y,
            "g_xy": self.g_xy,
            "nu_xy": self.nu_xy,
        }
        if self.g_xz is not None:
            data["g_xz"] = self.g_xz
        if self.g_yz is not None:
            data["g_yz"] = self.g_yz
        return data

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> Optional["OrthotropicPlateMaterial"]:
        if data is None:
            return None
        return cls(
            e_x=data["e_x"],
            e_y=data["e_y"],
            g_xy=data["g_xy"],
            nu_xy=data["nu_xy"],
            g_xz=data.get("g_xz"),
            g_yz=data.get("g_yz"),
        )


class Material:
    _material_counter = 1

    def __init__(
        self,
        name: str,
        e_mod: float,
        g_mod: float,
        density: float,
        yield_stress: float,
        orthotropic_plate: Optional[OrthotropicPlateMaterial] = None,
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
        self.orthotropic_plate = orthotropic_plate

    def to_dict(self):
        data = {
            "id": self.id,
            "name": self.name,
            "e_mod": self.e_mod,
            "g_mod": self.g_mod,
            "density": self.density,
            "yield_stress": self.yield_stress,
        }
        if self.orthotropic_plate is not None:
            data["orthotropic_plate"] = self.orthotropic_plate.to_dict()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Material":
        return cls(
            id=data.get("id"),
            name=data["name"],
            e_mod=data["e_mod"],
            g_mod=data["g_mod"],
            density=data["density"],
            yield_stress=data["yield_stress"],
            orthotropic_plate=OrthotropicPlateMaterial.from_dict(data.get("orthotropic_plate")),
        )

    @classmethod
    def reset_counter(cls):
        cls._material_counter = 1
