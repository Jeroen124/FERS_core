"""Plate free-vibration — simply-supported square plate (classical closed form).

Demonstrates that plate/shell elements now contribute mass to the modal mass
matrix (engine >= 0.2.43; before this, plate free-vibration was impossible). This
is NOT a numbered NAFEMS FVxx case (those plate frequencies are paywalled in
R0015); it validates the same capability against the textbook Navier solution.

SS square plate: side a = 1 m, thickness t = 0.01 m (a/t = 100, thin), E = 210 GPa,
nu = 0.3, rho = 7850. Transverse bending modes only (in-plane + drilling DOFs
fixed), so the spectrum is the classical
    f_mn = (pi/2) * (m^2 + n^2) * sqrt(D / (rho*t)) / a^2,  D = E t^3 / (12(1-nu^2)).
Fundamental f11 = (pi/a^2) * sqrt(D/(rho*t)) ~ 49.17 Hz. The low-order Mindlin/DSG3
element converges to it from above under mesh refinement.

Emits FVP.json (the wire model, with analysis.modal); the frequencies are computed
by the 0.2.43 engine (the published 0.2.42 wheel has no plate mass), so this script
does NOT solve — it only builds. Pass the mesh N as argv[1] (default 16).
"""

import sys
import os
import json
import math

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fers_core import FERS, Node, NodalSupport, Material, AnalysisOrder, Plate, SupportCondition

E, NU, RHO, T, A = 210e9, 0.3, 7850.0, 0.01, 1.0
G = E / (2 * (1 + NU))
D = E * T**3 / (12 * (1 - NU**2))
FC = math.sqrt(D / (RHO * T))


def f_mn(m, n):
    return 0.5 * math.pi * (m * m + n * n) * FC / (A * A)


FX = SupportCondition.fixed()
FR = SupportCondition.free()


def _sup(uz):
    # In-plane (X,Y) and drilling (Z-rot) fixed -> pure transverse bending spectrum.
    # uz fixed on the simply-supported edges, free in the interior; bending rotations free.
    return NodalSupport(
        displacement_conditions={"X": FX, "Y": FX, "Z": uz}, rotation_conditions={"X": FR, "Y": FR, "Z": FX}
    )


def build(n):
    c = FERS()
    c.settings.analysis_options.order = AnalysisOrder.LINEAR
    mat = Material(name="plate", e_mod=E, g_mod=G, density=RHO, yield_stress=235e6)
    step = A / n
    nd = {}
    for j in range(n + 1):
        for i in range(n + 1):
            edge = i in (0, n) or j in (0, n)
            nd[(i, j)] = Node(X=i * step, Y=j * step, Z=0.0, nodal_support=_sup(FX if edge else FR))
    for j in range(n):
        for i in range(n):
            n00, n10, n11, n01 = nd[(i, j)], nd[(i + 1, j)], nd[(i + 1, j + 1)], nd[(i, j + 1)]
            c.add_plate(
                Plate(
                    nodes=[n00, n10, n11],
                    material=mat,
                    thickness=T,
                    local_x_direction=(1, 0, 0),
                    theory="Mindlin",
                ),
                Plate(
                    nodes=[n00, n11, n01],
                    material=mat,
                    thickness=T,
                    local_x_direction=(1, 0, 0),
                    theory="Mindlin",
                ),
            )
    return c


def build_modal_dict(n, num_modes=6):
    d = build(n).to_dict(include_results=False)
    d["analysis"]["modal"] = {"num_modes": num_modes, "mass_formulation": "Consistent"}
    d["results"] = None
    return d


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 16
    d = build_modal_dict(n)
    here = os.path.dirname(__file__)
    with open(os.path.join(here, "FVP.json"), "w") as fh:
        json.dump(d, fh)
    plates = n * n * 2
    print(f"FVP.json written: {n}x{n} mesh, {plates} triangular plates")
    print(f"analytical targets (Hz): f11={f_mn(1, 1):.3f}  f12=f21={f_mn(1, 2):.3f}  f22={f_mn(2, 2):.3f}")


if __name__ == "__main__":
    main()
