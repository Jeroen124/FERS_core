"""NAFEMS FV1 — Pin-ended cross, in-plane vibration.

A planar "+" cross: 4 arms of length 5 m from a rigid centre, tips pinned. Same arm
geometry/material as FV2 (double cross), so the SAME four frequencies appear — but with
multiplicity 1/3/1/3 (single cross, 4 arms) instead of FV2's 1/7/1/7.

Targets (NAFEMS TNSB / R0015; derived closed-form, cross-checked vs FV2 theory):
  11.336 (×1, pinwheel), 17.709 (×3, clamped-pinned), 45.345 (×1), 57.390 (×3)
"""

import sys
import os
import json

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

E, RHO, NU = 200e9, 8000.0, 0.3
G = E / (2 * (1 + NU))
B = 0.125
A, I, J = B * B, B**4 / 12.0, 0.1406 * B**4
L_ARM, N_SEG, NUM_MODES = 5.0, 8, 12
TARGETS = [11.336, 17.709, 45.345, 57.39]

FX, FR = SupportCondition.fixed(), SupportCondition.free()


def _sup(ux, uy):
    return NodalSupport(
        displacement_conditions={"X": ux, "Y": uy, "Z": FX}, rotation_conditions={"X": FX, "Y": FX, "Z": FR}
    )


FREE, PIN = _sup(FR, FR), _sup(FX, FX)


def build():
    c = FERS()
    c.settings.analysis_options.order = AnalysisOrder.LINEAR
    mat = Material(name="FV1steel", e_mod=E, g_mod=G, density=RHO, yield_stress=235e6)
    sec = Section(name="SQ125", material=mat, i_y=I, i_z=I, j=J, area=A)
    centre = Node(0.0, 0.0, 0.0)
    centre.nodal_support = FREE
    members = []
    for dx, dy in [(1, 0), (0, 1), (-1, 0), (0, -1)]:
        prev = centre
        for s in range(1, N_SEG + 1):
            r = L_ARM * s / N_SEG
            nd = Node(r * dx, r * dy, 0.0)
            nd.nodal_support = PIN if s == N_SEG else FREE
            members.append(Member(start_node=prev, end_node=nd, section=sec))
            prev = nd
    c.add_member_set(MemberSet(members=members))
    return c


def main():
    c = build()
    freqs, _ = H.modal_frequencies(c, num_modes=NUM_MODES)
    print("FV1 computed (Hz):", [round(f, 4) for f in freqs])
    results, used = [], [False] * len(freqs)
    for t in TARGETS:
        k = min((j for j in range(len(freqs)) if not used[j]), key=lambda j: abs(freqs[j] - t))
        used[k] = True
        err = H.rel_err_pct(freqs[k], t)
        results.append(
            {
                "quantity": f"nearest mode to {t} Hz",
                "target": t,
                "fers": round(freqs[k], 4),
                "error_pct": round(err, 3),
                "unit": "Hz",
                "mesh_or_modes": f"{N_SEG} el/arm",
            }
        )
        print(f"TARGET {t:8.3f} -> FERS {freqs[k]:8.4f}  err {err:.3f}%")
    matched = all(r["error_pct"] < 2.0 for r in results)
    print("MATCHED (<2%):", matched)
    d = c.to_dict(include_results=False)
    for m in d["model"]["members"]:
        m["weight"] = 0.0
    d["analysis"]["modal"] = {"num_modes": NUM_MODES, "mass_formulation": "Consistent"}
    d["results"] = None
    here = os.path.dirname(__file__)
    json.dump(d, open(os.path.join(here, "FV1.json"), "w"))
    json.dump(
        {
            "id": "FV1",
            "results": results,
            "matched": matched,
            "all_frequencies": [round(f, 4) for f in freqs],
        },
        open(os.path.join(here, "FV1_result.json"), "w"),
        indent=2,
    )


if __name__ == "__main__":
    main()
