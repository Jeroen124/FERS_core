"""NAFEMS LE6 — Skew (Morley 30deg-acute rhombic) plate under uniform normal pressure.

Parallelogram A=(0,0) B=(1,0) C=(1.8660254,0.5) D=(0.8660254,0.5); side 1.0 m; t=0.01 m.
E=210 GPa, nu=0.3. Uniform pressure 700 Pa (-Z). Simply supported (w=0) on all 4 edges.
Target: max principal stress sigma_1 = 0.802 MPa at centre E=(0.9330127,0.25), lower surface.
Mindlin plate bending; stress from moment resultant: sigma = 6*M/t^2. Mesh-convergence sweep.
Published FE bracket the target (0.787-0.829), so a converged value lands within a few %.
"""

import sys
import os
import json
import math

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import nafems_harness as H
from fers_core import (
    FERS,
    Node,
    NodalSupport,
    Material,
    AnalysisOrder,
    Plate,
    LoadCase,
    SurfaceLoad,
    SurfaceLoadVertex,
    SupportCondition,
)

E, NU = 210e9, 0.3
G = E / (2 * (1 + NU))
T = 0.01
Q = 700.0
A = (0.0, 0.0)
Bc = (1.0, 0.0)
D = (0.8660254, 0.5)  # C = Bc + (D-A)
E_CENTRE = (0.9330127, 0.25)
TARGET = 0.802e6  # Pa

FX = SupportCondition.fixed()
FR = SupportCondition.free()


def _sup(ux, uy):
    return NodalSupport(
        displacement_conditions={"X": ux, "Y": uy, "Z": FX},  # uz=0 (SS transverse)
        rotation_conditions={"X": FR, "Y": FR, "Z": FR},
    )  # soft SS: rotations free


def build(N):
    c = FERS()
    c.settings.analysis_options.order = AnalysisOrder.LINEAR
    mat = Material(name="LE6steel", e_mod=E, g_mod=G, density=7800, yield_stress=235e6)
    ux0, uy0 = Bc[0] - A[0], Bc[1] - A[1]  # B-A
    vx0, vy0 = D[0] - A[0], D[1] - A[1]  # D-A
    nd = {}
    for j in range(N + 1):
        for i in range(N + 1):
            u, v = i / N, j / N
            x = A[0] + u * ux0 + v * vx0
            y = A[1] + u * uy0 + v * vy0
            support = None
            edge = (i in (0, N)) or (j in (0, N))
            if edge:
                if i == 0 and j == 0:  # corner A: ux=uy=0
                    support = _sup(FX, FX)
                elif i == N and j == 0:  # corner B: uy=0
                    support = _sup(FR, FX)
                else:
                    support = _sup(FR, FR)  # other edges: only uz=0
            nd[(i, j)] = Node(X=x, Y=y, Z=0.0, nodal_support=support)
    for j in range(N):
        for i in range(N):
            n00, n10 = nd[(i, j)], nd[(i + 1, j)]
            n11, n01 = nd[(i + 1, j + 1)], nd[(i, j + 1)]
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
    lc = LoadCase(name="P")
    SurfaceLoad(
        load_case=lc,
        magnitude=Q,
        direction=(0, 0, -1),
        polygon=[
            SurfaceLoadVertex(A[0], A[1], 0),
            SurfaceLoadVertex(Bc[0], Bc[1], 0),
            SurfaceLoadVertex(D[0] + ux0, D[1] + uy0, 0),
            SurfaceLoadVertex(D[0], D[1], 0),
        ],
    )
    c.add_load_case(lc)
    return c


def principal_sigma1_at_centre(res):
    """Find plate whose centroid is nearest E, return sigma_1 (Pa) from its moment resultants."""
    pr = res["loadcases"]["P"]["plate_results"]
    best, bestd = None, 1e9
    for p in pr.values():
        cen = p["centroid"]
        dx = cen["X"] - E_CENTRE[0]
        dy = cen["Y"] - E_CENTRE[1]
        d = dx * dx + dy * dy
        if d < bestd:
            bestd, best = d, p
    r = best["resultants"]
    mx, my, mxy = r["mx"], r["my"], r["mxy"]
    m1 = (mx + my) / 2 + math.sqrt(((mx - my) / 2) ** 2 + mxy**2)
    return H.bending_stress(m1, T), best


def main():
    rows = []
    last = None
    for N in (8, 16, 24, 32, 48):
        c = build(N)
        res = H.static_results(c)
        s1, _ = principal_sigma1_at_centre(res)
        err = H.rel_err_pct(s1, TARGET)
        rows.append((N, s1, err))
        print(f"N={N:2d}  sigma_1(E) = {s1 / 1e6:.4f} MPa   target 0.802   err {err:.2f}%")
        last = (N, c, s1, err)
    conv = ", ".join(f"{N}x{N}:{e:.1f}%" for N, _, e in rows)
    # Richardson extrapolation to h->0 (h~1/N) from the three finest meshes, fitting
    # sigma(h) = sigma_inf - C*h^p. Estimate the observed order p by bisection on the
    # ratio identity, then extrapolate. Purely a post-processing diagnostic.
    (n1, s_1, _), (n2, s_2, _), (n3, s_3, _) = rows[-3], rows[-2], rows[-1]
    h1, h2, h3 = 1.0 / n1, 1.0 / n2, 1.0 / n3
    R = (s_2 - s_1) / (s_3 - s_2)  # = (h1^p - h2^p)/(h2^p - h3^p)

    def f(p):
        return (h1**p - h2**p) / (h2**p - h3**p) - R

    lo, hi, s_inf, p = 0.3, 4.0, s_3, None
    if f(lo) * f(hi) < 0:
        for _ in range(80):
            mid = 0.5 * (lo + hi)
            if f(lo) * f(mid) <= 0:
                hi = mid
            else:
                lo = mid
        p = 0.5 * (lo + hi)
        C = (s_2 - s_1) / (h1**p - h2**p)
        s_inf = s_3 + C * h3**p
    rich_err = H.rel_err_pct(s_inf, TARGET)
    porder = f"{p:.2f}" if p else "n/a"
    print(
        f"Richardson-extrapolated sigma_1(E) = {s_inf / 1e6:.4f} MPa  (order p~{porder})  err {rich_err:.2f}%"
    )
    conv += f"; Richardson->{s_inf / 1e6:.3f}MPa ({rich_err:.1f}%)"
    matched = rich_err < 5.0 or last[3] < 8.0  # converges to target within a few %
    print("convergence:", conv, " matched:", matched)

    # Emit a browser/WASM-safe mesh for the live site (<=2048 plates); the finer 48x48
    # (4608 plates) exceeds the in-browser WASM ceiling. The convergence table below
    # carries the refined offline result.
    N_LIVE = 32
    c_live = build(N_LIVE)
    res_live = H.static_results(c_live)
    s_live, _ = principal_sigma1_at_centre(res_live)
    err_live = H.rel_err_pct(s_live, TARGET)
    d = c_live.to_dict(include_results=False)
    d["results"] = None
    here = os.path.dirname(__file__)
    with open(os.path.join(here, "LE6.json"), "w") as fh:
        json.dump(d, fh)
    with open(os.path.join(here, "LE6_result.json"), "w") as fh:
        json.dump(
            {
                "id": "LE6",
                "results": [
                    {
                        "quantity": "max principal stress sigma_1 at centre E, lower surface",
                        "target": TARGET,
                        "fers": round(s1, 1),
                        "error_pct": round(err, 3),
                        "unit": "Pa",
                        "mesh_or_modes": f"{last[0]}x{last[0]} Mindlin (offline)",
                    }
                ],
                "live": {
                    "fers": round(s_live, 1),
                    "error_pct": round(err_live, 3),
                    "mesh": f"{N_LIVE}x{N_LIVE}",
                    "plates": N_LIVE * N_LIVE * 2,
                },
                "convergence": conv,
                "matched": matched,
            },
            fh,
            indent=2,
        )


if __name__ == "__main__":
    main()
