"""NAFEMS FV6 — Circular ring, in-plane and out-of-plane flexural vibration (free-free).

Complete circular ring, centroidal radius R=1.0 m, solid circular section r_c=0.05 m,
E=200 GPa, ν=0.3, ρ=8000. Modelled as N straight beam segments. Free-free in 3D → 6 rigid-body
modes; lifted with soft translational grounding springs at three well-separated nodes.

Targets — classical thin-ring closed form (independently verified), pairs per wavenumber n:
  out-of-plane flexural-torsional n=2/3/4: 51.849 / 148.77 / 286.98 Hz
  in-plane flexural            n=2/3/4: 53.382 / 150.99 / 289.51 Hz
(NAFEMS R0015 FE targets are ~1% higher: 52.29/149.7/288.3 and 53.97/152.4/288.3.)
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
    Member,
    MemberSet,
    NodalSupport,
    Material,
    Section,
    AnalysisOrder,
    SupportCondition,
)

E, NU, RHO = 200e9, 0.3, 8000.0
G = E / (2 * (1 + NU))
R = 1.0
RC = 0.05
A = math.pi * RC**2
I = math.pi * RC**4 / 4
Jt = math.pi * RC**4 / 2
KAPPA = 6 * (1 + NU) / (7 + 6 * NU)
ASH = KAPPA * A
N_SEG = 60
NUM_MODES = 20
K_SOFT = 50.0
# classical thin-ring closed-form targets (verified)
TARGETS = [51.849, 53.382, 148.77, 150.99, 286.98, 289.51]
NAFEMS_FE = {51.849: 52.29, 53.382: 53.97, 148.77: 149.7, 150.99: 152.4, 286.98: 288.3, 289.51: 288.3}

FX, FR = SupportCondition.fixed(), SupportCondition.free()


def grounded(k):
    s = SupportCondition.spring(k)
    return NodalSupport(
        displacement_conditions={"X": s, "Y": s, "Z": s}, rotation_conditions={"X": FR, "Y": FR, "Z": FR}
    )


def build(n_seg=N_SEG, k_soft=0.0):
    # Native free-free (fers_calculations >= 0.2.42): the modal spectral shift
    # solves the singular K, so no grounding springs are needed. Pass k_soft > 0
    # only for an older wheel without the shift.
    c = FERS()
    c.settings.analysis_options.order = AnalysisOrder.LINEAR
    mat = Material(name="FV6steel", e_mod=E, g_mod=G, density=RHO, yield_stress=235e6)
    sec = Section(name="CIRC", material=mat, i_y=I, i_z=I, j=Jt, area=A, a_sy=ASH, a_sz=ASH)
    ground_idx = {0, n_seg // 3, 2 * n_seg // 3} if k_soft > 0.0 else set()
    nodes = []
    for k in range(n_seg):
        th = 2 * math.pi * k / n_seg
        nd = Node(R * math.cos(th), R * math.sin(th), 0.0)
        if k in ground_idx:
            nd.nodal_support = grounded(k_soft)
        nodes.append(nd)
    members = [
        Member(start_node=nodes[k], end_node=nodes[(k + 1) % n_seg], section=sec) for k in range(n_seg)
    ]
    c.add_member_set(MemberSet(members=members))
    return c


def main():
    c = build()
    freqs, _ = H.modal_frequencies(c, num_modes=NUM_MODES)
    flex = [f for f in freqs if f > 5.0]  # drop the 6 near-zero rigid-body modes
    n_rigid = len(freqs) - len(flex)
    print(f"FV6 rigid-body modes (<5 Hz): {n_rigid}")
    print("FV6 flexural (Hz):", [round(f, 3) for f in flex[:12]])
    results, used = [], [False] * len(flex)
    for t in TARGETS:
        k = min((j for j in range(len(flex)) if not used[j]), key=lambda j: abs(flex[j] - t))
        used[k] = True
        err = H.rel_err_pct(flex[k], t)
        results.append(
            {
                "quantity": f"ring flexural ~{t} Hz",
                "target": t,
                "fers": round(flex[k], 3),
                "error_pct": round(err, 3),
                "unit": "Hz",
                "mesh_or_modes": f"{N_SEG} segments",
                "nafems_fe": NAFEMS_FE[t],
            }
        )
        print(f"TARGET {t:8.3f} (NAFEMS FE {NAFEMS_FE[t]:6.2f}) -> FERS {flex[k]:8.3f}  err {err:.3f}%")
    matched = all(r["error_pct"] < 2.0 for r in results) and n_rigid == 6
    print("MATCHED (<2% vs closed-form, 6 rigid modes):", matched)
    d = c.to_dict(include_results=False)
    for m in d["model"]["members"]:
        m["weight"] = 0.0
    d["analysis"]["modal"] = {"num_modes": NUM_MODES, "mass_formulation": "Consistent"}
    d["results"] = None
    here = os.path.dirname(__file__)
    json.dump(d, open(os.path.join(here, "FV6.json"), "w"))
    json.dump(
        {
            "id": "FV6",
            "results": results,
            "matched": matched,
            "n_rigid_body": n_rigid,
            "all_frequencies": [round(f, 3) for f in freqs],
        },
        open(os.path.join(here, "FV6_result.json"), "w"),
        indent=2,
    )


if __name__ == "__main__":
    main()
