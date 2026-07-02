"""Golden, verified templates for building NAFEMS-style benchmark models through
the FERS solver. Every pattern here has been checked against a closed-form result.

Run:  python reference_examples.py   (from FERS_core/, with the venv active)

Key gotchas these templates encode
----------------------------------
1. MODAL MASS: set every member ``weight = 0`` (the harness does this) so the
   solver derives mass from ``density * area``. The Python builder otherwise
   auto-fills ``weight`` with the element mass, which the solver misreads as a
   force/length and divides by g -> wrong frequencies.
2. PLANARIZATION: for an in-plane-only vibration problem, constrain the
   out-of-plane translation + the two out-of-plane rotations + torsion at every
   node, leaving only the in-plane bending DOF free, so spurious out-of-plane
   modes don't crowd the spectrum.
3. PLATE BENDING: use ``theory="Mindlin"``. The Kirchhoff/DKT path is currently
   unreliable (grossly under-stiff on these tests). Mindlin converges from the
   stiff side (~7% at 16x16, improving with refinement) toward thin-plate theory.
4. PLATE STRESS: the solver returns stress RESULTANTS (nx.. [N/m], mx.. [N.m/m]).
   Recover stress with sigma_membrane = N/t and sigma_bending = 6M/t^2.
5. PLATE MODAL IS UNSUPPORTED: the modal mass matrix is assembled from members
   only, so plate/shell free-vibration has no mass -> do NOT attempt plate FV.
"""
from __future__ import annotations

import math
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
import nafems_harness as H  # noqa: E402

from fers_core import (  # noqa: E402
    FERS, Node, Member, MemberSet, NodalSupport, Material, Section,
    AnalysisOrder, Plate, LoadCase, SurfaceLoad, SurfaceLoadVertex, SupportCondition,
)


def steel(E=210e9, G=80.769e9, rho=7850.0):
    return Material(name="Steel", e_mod=E, g_mod=G, density=rho, yield_stress=235e6)


# --- Template 1: cantilever beam natural frequency (Euler-Bernoulli) ----------

def cantilever_modal():
    E, rho, b, L, n_el = 210e9, 7850.0, 0.1, 5.0, 12
    A, I, J = b * b, b**4 / 12.0, 0.1406 * b**4
    c = FERS()
    c.settings.analysis_options.order = AnalysisOrder.LINEAR
    sec = Section(name="SQ", material=steel(E, rho=rho), i_y=I, i_z=I, j=J, area=A)
    nodes = [Node(L * i / n_el, 0.0, 0.0) for i in range(n_el + 1)]
    nodes[0].nodal_support = NodalSupport()  # fully fixed
    c.add_member_set(MemberSet(members=[
        Member(start_node=nodes[i], end_node=nodes[i + 1], section=sec) for i in range(n_el)]))
    freqs, _ = H.modal_frequencies(c, num_modes=4)
    f1 = 1.875104**2 / (2 * math.pi) * math.sqrt(E * I / (rho * A * L**4))
    print(f"[cantilever]  f1 FERS={freqs[0]:.4f} Hz  target={f1:.4f}  err={H.rel_err_pct(freqs[0], f1):.3f}%")


# --- Template 2: in-plane simply-supported beam (planarized) ------------------

def simply_supported_modal():
    E, rho, b, L, n_el = 210e9, 7850.0, 0.1, 10.0, 12
    A, I, J = b * b, b**4 / 12.0, 0.1406 * b**4
    c = FERS()
    c.settings.analysis_options.order = AnalysisOrder.LINEAR
    sec = Section(name="SQ", material=steel(E, rho=rho), i_y=I, i_z=I, j=J, area=A)
    nodes = [Node(L * i / n_el, 0.0, 0.0) for i in range(n_el + 1)]
    # Planarize: free only Y-translation (roller) + RZ (in-plane bending).
    pin = NodalSupport(
        displacement_conditions={"X": SupportCondition.fixed(), "Y": SupportCondition.fixed(), "Z": SupportCondition.fixed()},
        rotation_conditions={"X": SupportCondition.fixed(), "Y": SupportCondition.fixed(), "Z": SupportCondition.free()})
    roller = NodalSupport(
        displacement_conditions={"X": SupportCondition.free(), "Y": SupportCondition.fixed(), "Z": SupportCondition.fixed()},
        rotation_conditions={"X": SupportCondition.fixed(), "Y": SupportCondition.fixed(), "Z": SupportCondition.free()})
    interior = NodalSupport(
        displacement_conditions={"X": SupportCondition.free(), "Y": SupportCondition.free(), "Z": SupportCondition.fixed()},
        rotation_conditions={"X": SupportCondition.fixed(), "Y": SupportCondition.fixed(), "Z": SupportCondition.free()})
    nodes[0].nodal_support = pin
    nodes[-1].nodal_support = roller
    for nd in nodes[1:-1]:
        nd.nodal_support = interior
    c.add_member_set(MemberSet(members=[
        Member(start_node=nodes[i], end_node=nodes[i + 1], section=sec) for i in range(n_el)]))
    freqs, _ = H.modal_frequencies(c, num_modes=3)
    f1 = math.pi**2 / (2 * math.pi) * math.sqrt(E * I / (rho * A * L**4))
    print(f"[simple-sup]  f1 FERS={freqs[0]:.4f} Hz  target={f1:.4f}  err={H.rel_err_pct(freqs[0], f1):.3f}%")


# --- Template 3: simply-supported square plate, uniform pressure (Mindlin) ----

def ss_square_plate(N=16):
    E, G, a, t, q = 210e9, 80.769e9, 1.0, 0.01, 1000.0
    nu = E / (2 * G) - 1.0
    D = E * t**3 / (12 * (1 - nu**2))
    w_target = 0.00406 * q * a**4 / D  # Timoshenko thin-plate SS uniform load
    c = FERS()
    c.settings.analysis_options.order = AnalysisOrder.LINEAR
    mat = steel(E, G)
    ss = NodalSupport(
        displacement_conditions={"X": SupportCondition.free(), "Y": SupportCondition.free(), "Z": SupportCondition.fixed()},
        rotation_conditions={"X": SupportCondition.free(), "Y": SupportCondition.free(), "Z": SupportCondition.free()})
    nd = {}
    for iy in range(N + 1):
        for ix in range(N + 1):
            edge = ix in (0, N) or iy in (0, N)
            nd[(ix, iy)] = Node(X=a * ix / N, Y=a * iy / N, Z=0.0, nodal_support=ss if edge else None)
    for iy in range(N):
        for ix in range(N):
            n00, n10 = nd[(ix, iy)], nd[(ix + 1, iy)]
            n11, n01 = nd[(ix + 1, iy + 1)], nd[(ix, iy + 1)]
            c.add_plate(
                Plate(nodes=[n00, n10, n11], material=mat, thickness=t, local_x_direction=(1, 0, 0), theory="Mindlin"),
                Plate(nodes=[n00, n11, n01], material=mat, thickness=t, local_x_direction=(1, 0, 0), theory="Mindlin"))
    lc = LoadCase(name="P")
    SurfaceLoad(load_case=lc, magnitude=q, direction=(0, 0, -1), polygon=[
        SurfaceLoadVertex(0, 0, 0), SurfaceLoadVertex(a, 0, 0), SurfaceLoadVertex(a, a, 0), SurfaceLoadVertex(0, a, 0)])
    c.add_load_case(lc)
    res = H.static_results(c)
    disp = res["loadcases"]["P"]["displacement_nodes"]
    wc = disp[str(nd[(N // 2, N // 2)].id)]["dz"]
    print(f"[ss-plate N={N}] w_center FERS={wc:.6e}  target={-w_target:.6e}  err={H.rel_err_pct(wc, -w_target):.2f}%")


if __name__ == "__main__":
    cantilever_modal()
    simply_supported_modal()
    ss_square_plate(8)
    ss_square_plate(16)
