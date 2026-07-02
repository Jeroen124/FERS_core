"""NAFEMS FV2 — Pin-ended double cross, in-plane vibration.

8 straight arms of length 5 m radiating from a central rigid joint C=(5,5) at 45deg
increments (= four 10 m beams crossing at their midpoint). Square 0.125x0.125 section.
Tips pinned (ux=uy=0). In-plane spectrum isolated by fixing uz, theta_x, theta_y everywhere.

Targets (NAFEMS TNSB Rev.3, Euler-Bernoulli theory; corroborated Abaqus/DIANA/Altair):
  mode 1        : 11.336 Hz  (pinwheel: arms pinned-pinned, centre rotates)
  modes 2-8  x7 : 17.709 Hz  (arm bending, centre clamped -> clamped-pinned)
  mode 9        : 45.345 Hz  (2nd pinwheel)
  modes 10-16 x7: 57.390 Hz  (2nd clamped-pinned)
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

E, RHO, NU = 200e9, 8000.0, 0.3
G = E / (2 * (1 + NU))
B = 0.125
A = B * B
I = B**4 / 12.0
J = 0.1406 * B**4
L_ARM = 5.0
CX, CY = 5.0, 5.0
N_SEG = 8  # elements per arm
NUM_MODES = 20
TARGETS = [11.336, 17.709, 45.345, 57.390]


# In-plane planarization support factories (free DOFs: ux, uy, theta_z as noted).
def _sup(ux, uy):
    return NodalSupport(
        displacement_conditions={"X": ux, "Y": uy, "Z": SupportCondition.fixed()},
        rotation_conditions={
            "X": SupportCondition.fixed(),
            "Y": SupportCondition.fixed(),
            "Z": SupportCondition.free(),
        },
    )


FREE = _sup(SupportCondition.free(), SupportCondition.free())  # interior + centre
PIN = _sup(SupportCondition.fixed(), SupportCondition.fixed())  # arm tip: ux=uy=0


def build():
    c = FERS()
    c.settings.analysis_options.order = AnalysisOrder.LINEAR
    mat = Material(name="FV2steel", e_mod=E, g_mod=G, density=RHO, yield_stress=235e6)
    sec = Section(name="SQ125", material=mat, i_y=I, i_z=I, j=J, area=A)

    centre = Node(CX, CY, 0.0)
    centre.nodal_support = FREE
    members = []
    for k in range(8):
        ang = math.radians(45.0 * k)
        dx, dy = math.cos(ang), math.sin(ang)
        prev = centre
        for s in range(1, N_SEG + 1):
            r = L_ARM * s / N_SEG
            nd = Node(CX + r * dx, CY + r * dy, 0.0)
            nd.nodal_support = PIN if s == N_SEG else FREE
            members.append(Member(start_node=prev, end_node=nd, section=sec))
            prev = nd
    c.add_member_set(MemberSet(members=members))
    return c


def main():
    c = build()
    freqs, modal = H.modal_frequencies(c, num_modes=NUM_MODES)
    # Match each distinct target to the nearest computed frequency, and count multiplicity.
    print("NAFEMS FV2 — first %d computed frequencies (Hz):" % NUM_MODES)
    for i, f in enumerate(freqs):
        print("  mode %2d: %8.4f" % (i + 1, f))
    results = []
    used = [False] * len(freqs)
    for t in TARGETS:
        # nearest unused frequency
        best = min((j for j in range(len(freqs)) if not used[j]), key=lambda j: abs(freqs[j] - t))
        used[best] = True
        err = H.rel_err_pct(freqs[best], t)
        results.append(
            {
                "quantity": f"nearest mode to {t} Hz",
                "target": t,
                "fers": round(freqs[best], 4),
                "error_pct": round(err, 3),
                "unit": "Hz",
                "mesh_or_modes": f"{N_SEG} el/arm, {NUM_MODES} modes",
            }
        )
        print(f"TARGET {t:8.3f} Hz -> FERS {freqs[best]:8.4f} Hz  err {err:.3f}%")
    matched = all(r["error_pct"] < 2.0 for r in results)
    print("MATCHED (<2%%): %s" % matched)

    # Emit reusable solver input (weight=0, analysis.modal) + machine-readable result.
    d = c.to_dict(include_results=False)
    for m in d["model"]["members"]:
        m["weight"] = 0.0
    d["analysis"]["modal"] = {"num_modes": NUM_MODES, "mass_formulation": "Consistent"}
    d["results"] = None
    here = os.path.dirname(__file__)
    with open(os.path.join(here, "FV2.json"), "w") as fh:
        json.dump(d, fh)
    with open(os.path.join(here, "FV2_result.json"), "w") as fh:
        json.dump(
            {
                "id": "FV2",
                "results": results,
                "matched": matched,
                "all_frequencies": [round(f, 4) for f in freqs],
            },
            fh,
            indent=2,
        )


if __name__ == "__main__":
    main()
