"""Post-publish smoke check for the dynamics release (F1/F2/F4).

Run AFTER the new solver wheel is published/installed:
    python tests/nafems/verify_release.py   (from FERS_core/, venv active)

Against the pre-F2 wheel these will report NOT-PRESENT (free-free crashes; the
nodal mass is ignored; plate shear is 0). Against the new wheel all three PASS.
"""

import sys
import os
import math

sys.path.insert(0, os.path.dirname(__file__))
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
    Plate,
    LoadCase,
    SurfaceLoad,
    SurfaceLoadVertex,
    SupportCondition,
    NodalMass,
)

E, RHO, B = 210e9, 7850.0, 0.1


def steel():
    return Material(name="S", e_mod=E, g_mod=80.769e9, density=RHO, yield_stress=235e6)


def f1_free_free_beam():
    """F1: a free-free (unsupported) planar beam must SOLVE (was a crash) and
    return 3 in-plane rigid-body modes near 0."""
    L, N = 5.0, 12
    A, I, J = B * B, B**4 / 12, 0.1406 * B**4
    c = FERS()
    c.settings.analysis_options.order = AnalysisOrder.LINEAR
    sec = Section(name="SQ", material=steel(), i_y=I, i_z=I, j=J, area=A)
    FX, FR = SupportCondition.fixed(), SupportCondition.free()
    plan = NodalSupport(
        displacement_conditions={"X": FR, "Y": FR, "Z": FX}, rotation_conditions={"X": FX, "Y": FX, "Z": FR}
    )
    nodes = [Node(L * i / N, 0, 0) for i in range(N + 1)]
    for nd in nodes:
        nd.nodal_support = plan
    c.add_member_set(
        MemberSet(members=[Member(start_node=nodes[i], end_node=nodes[i + 1], section=sec) for i in range(N)])
    )
    try:
        freqs, _ = H.modal_frequencies(c, num_modes=6)
    except Exception as e:
        return False, f"free-free modal FAILED (F1 not in wheel): {str(e)[:80]}"
    n_rigid = sum(1 for f in freqs if f < 1.0)
    return (
        n_rigid == 3,
        f"free-free solved; {n_rigid} rigid-body modes (expect 3); freqs={[round(f, 3) for f in freqs[:6]]}",
    )


def f2_nodal_mass():
    """F2: a heavy tip nodal mass must drop the cantilever fundamental far below
    the bare 3.34 Hz (to ~0.33 Hz)."""
    L, N = 5.0, 10
    A, I, J = B * B, B**4 / 12, 0.1406 * B**4
    c = FERS()
    c.settings.analysis_options.order = AnalysisOrder.LINEAR
    sec = Section(name="SQ", material=steel(), i_y=I, i_z=I, j=J, area=A)
    nodes = [Node(L * i / N, 0, 0) for i in range(N + 1)]
    nodes[0].nodal_support = NodalSupport()
    c.add_member_set(
        MemberSet(members=[Member(start_node=nodes[i], end_node=nodes[i + 1], section=sec) for i in range(N)])
    )
    c.add_nodal_mass(NodalMass(node=nodes[-1], mass=10_000.0))
    freqs, _ = H.modal_frequencies(c, num_modes=3)
    k = 3 * E * I / L**3
    f_target = (k / 10_000.0) ** 0.5 / (2 * math.pi)  # ~0.325 Hz (tip-mass dominated)
    ok = freqs[0] < 0.5 and abs(freqs[0] - f_target) / f_target < 0.10
    return (
        ok,
        f"tip-mass f1={freqs[0]:.4f} Hz (bare 3.34, target ~{f_target:.3f}) -> {'APPLIED' if freqs[0] < 0.5 else 'IGNORED (F2 not in wheel)'}",  # noqa: E501
    )


def f4_plate_shear():
    """F4: a loaded plate strip must report a NONZERO transverse shear Qx."""
    LEN, WID, T, NX = 2.0, 0.2, 0.1, 8
    c = FERS()
    c.settings.analysis_options.order = AnalysisOrder.LINEAR
    mat = steel()
    fix = NodalSupport()
    cols = []
    for ix in range(NX + 1):
        s = fix if ix == 0 else None
        cols.append(
            (
                Node(X=LEN * ix / NX, Y=0.0, Z=0.0, nodal_support=s),
                Node(X=LEN * ix / NX, Y=WID, Z=0.0, nodal_support=s),
            )
        )
    for ix in range(NX):
        n00, n01 = cols[ix]
        n10, n11 = cols[ix + 1]
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
        magnitude=1000.0,
        direction=(0, 0, -1),
        polygon=[
            SurfaceLoadVertex(0, 0, 0),
            SurfaceLoadVertex(LEN, 0, 0),
            SurfaceLoadVertex(LEN, WID, 0),
            SurfaceLoadVertex(0, WID, 0),
        ],
    )
    c.add_load_case(lc)
    res = H.static_results(c)
    qx = max(abs(p["resultants"]["qx"]) for p in res["loadcases"]["P"]["plate_results"].values())
    return qx > 1e-6, f"max |Qx| = {qx:.2f} N/m -> {'RECOVERED' if qx > 1e-6 else 'ZERO (F4 not in wheel)'}"


if __name__ == "__main__":
    checks = [
        ("F1 free-free modal", f1_free_free_beam),
        ("F2 nodal point mass", f2_nodal_mass),
        ("F4 plate Qx shear", f4_plate_shear),
    ]
    all_ok = True
    for name, fn in checks:
        try:
            ok, msg = fn()
        except Exception as e:
            ok, msg = False, f"raised: {str(e)[:120]}"
        all_ok &= ok
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {msg}")
    print("\nRELEASE OK" if all_ok else "\nSOME CHECKS FAILED (expected against a pre-release wheel)")
    sys.exit(0 if all_ok else 1)
