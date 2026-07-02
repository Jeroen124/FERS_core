"""NAFEMS FV3 — Free square frame, in-plane vibration (free-free).

Closed 10 m × 10 m square frame, 4 rigid-jointed 10 m sides, solid 0.25 × 0.25 m square
section, E=200 GPa, ρ=8000. Completely free → 3 in-plane rigid-body modes (~0 Hz) then the
elastic spectrum. In-plane isolation: fix uz, θx, θy at every node.

Targets (converged Euler-Bernoulli; cross-checked vs NAFEMS R0015 via Autodesk republication):
  rigid body ×3 (0 Hz), then 3.2616, 5.6652, 11.1424(×2), 12.8201, 24.6001, 28.6665(×2), 38.9328
"""
import sys, os, json, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import nafems_harness as H
from fers_core import (FERS, Node, Member, MemberSet, NodalSupport, Material, Section,
                       AnalysisOrder, SupportCondition)

E, RHO, NU = 200e9, 8000.0, 0.29
G = E / (2 * (1 + NU))
D = 0.25
A, I, J = D * D, D**4 / 12.0, 0.1406 * D**4
SIDE, N_SIDE, NUM_MODES = 10.0, 20, 12
# elastic targets (skip the 3 rigid-body zeros)
TARGETS = [3.2616, 5.6652, 11.1424, 12.8201, 24.6001, 28.6665, 38.9328]

FX, FR = SupportCondition.fixed(), SupportCondition.free()
# In-plane isolation (uz, rx, ry fixed); ux, uy, rz FREE (free-free in plane).
INPLANE = NodalSupport(
    displacement_conditions={"X": FR, "Y": FR, "Z": FX},
    rotation_conditions={"X": FX, "Y": FX, "Z": FR})

# FERS's modal eigensolver Cholesky-factorises K, so a truly free-free (singular K)
# model fails ("reduced K* lost positive-definiteness"). We lift the 3 in-plane
# rigid-body modes with tiny grounding springs at two opposite corners (ux,uy). At
# k_soft ~ 1e3 N/m the rigid-body modes sit far below the first elastic mode (3.26 Hz)
# and the elastic spectrum is unchanged to <0.01%.
K_SOFT = 10.0

def grounded(k):
    return NodalSupport(
        displacement_conditions={"X": SupportCondition.spring(k), "Y": SupportCondition.spring(k), "Z": FX},
        rotation_conditions={"X": FX, "Y": FX, "Z": FR})

def build(k_soft=0.0):
    # Native free-free: the solver's modal spectral shift (fers_calculations
    # >= 0.2.42) factorises the singular K directly, so NO grounding springs are
    # needed. Pass k_soft > 0 only to run against an older wheel without the shift.
    c = FERS()
    c.settings.analysis_options.order = AnalysisOrder.LINEAR
    mat = Material(name="FV3steel", e_mod=E, g_mod=G, density=RHO, yield_stress=235e6)
    sec = Section(name="SQ250", material=mat, i_y=I, i_z=I, j=J, area=A)
    corner_xy = [(0, 0), (SIDE, 0), (SIDE, SIDE), (0, SIDE)]
    corner_nodes = [Node(x, y, 0.0) for x, y in corner_xy]
    for i, n in enumerate(corner_nodes):
        n.nodal_support = grounded(k_soft) if (k_soft > 0.0 and i in (0, 2)) else INPLANE
    members = []
    for ci in range(4):
        a = corner_nodes[ci]
        b = corner_nodes[(ci + 1) % 4]
        prev = a
        for s in range(1, N_SIDE + 1):
            if s == N_SIDE:
                nd = b
            else:
                x = a.X + (b.X - a.X) * s / N_SIDE
                y = a.Y + (b.Y - a.Y) * s / N_SIDE
                nd = Node(x, y, 0.0)
                nd.nodal_support = INPLANE
            members.append(Member(start_node=prev, end_node=nd, section=sec))
            prev = nd
    c.add_member_set(MemberSet(members=members))
    return c

def main():
    c = build()
    freqs, _ = H.modal_frequencies(c, num_modes=NUM_MODES)
    print("FV3 raw computed (Hz):", [round(f, 4) for f in freqs])
    # drop rigid-body modes: everything below ~1 Hz
    elastic = [f for f in freqs if f > 1.0]
    n_rigid = len(freqs) - len(elastic)
    print(f"rigid-body modes (<1 Hz): {n_rigid}")
    results, used = [], [False] * len(elastic)
    for t in TARGETS:
        k = min((j for j in range(len(elastic)) if not used[j]), key=lambda j: abs(elastic[j] - t))
        used[k] = True
        err = H.rel_err_pct(elastic[k], t)
        results.append({"quantity": f"elastic mode ~{t} Hz", "target": t, "fers": round(elastic[k], 4),
                        "error_pct": round(err, 3), "unit": "Hz", "mesh_or_modes": f"{N_SIDE} el/side"})
        print(f"TARGET {t:8.3f} -> FERS {elastic[k]:8.4f}  err {err:.3f}%")
    matched = all(r["error_pct"] < 2.0 for r in results) and n_rigid == 3
    print("MATCHED (<2%, 3 rigid modes):", matched)
    d = c.to_dict(include_results=False)
    for m in d["model"]["members"]:
        m["weight"] = 0.0
    d["analysis"]["modal"] = {"num_modes": NUM_MODES, "mass_formulation": "Consistent"}
    d["results"] = None
    here = os.path.dirname(__file__)
    json.dump(d, open(os.path.join(here, "FV3.json"), "w"))
    json.dump({"id": "FV3", "results": results, "matched": matched, "n_rigid_body": n_rigid,
               "all_frequencies": [round(f, 4) for f in freqs]},
              open(os.path.join(here, "FV3_result.json"), "w"), indent=2)

if __name__ == "__main__":
    main()
