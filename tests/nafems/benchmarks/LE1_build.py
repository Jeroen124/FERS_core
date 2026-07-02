"""NAFEMS LE1 — Elliptic membrane (plane stress).

Quarter elliptic annulus, 1st quadrant. Inner ellipse (a=2.0, b=1.0), outer (a=3.25, b=2.75),
thickness t=0.1 m. E=210 GPa, nu=0.3. Uniform OUTWARD normal traction 10 MPa on the outer arc.
Symmetry: ux=0 on x=0 edge (AB), uy=0 on y=0 edge (CD). Target: sigma_yy = 92.7 MPa at D=(2,0).

Membrane (in-plane) problem: recover sigma_yy = ny / t. Out-of-plane DOFs planarized.
CST/low-order membrane converges slowly at the stress point D -> mesh-convergence sweep.
"""
import sys, os, json, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import nafems_harness as H
from fers_core import (FERS, Node, NodalSupport, Material, AnalysisOrder, Plate,
                       LoadCase, NodalLoad, SupportCondition)

E, NU, T = 210e9, 0.3, 0.1
G = E / (2 * (1 + NU))
AI, BI = 2.0, 1.0       # inner ellipse semi-axes
AO, BO = 3.25, 2.75     # outer ellipse semi-axes
P = 10e6                 # outward normal traction [Pa]
D_PT = (2.0, 0.0)
TARGET = 92.7e6          # Pa (sigma_yy at D)

FX, FR = SupportCondition.fixed(), SupportCondition.free()

def _sup(ux, uy):
    # Planarize: only ux,uy live (membrane). uz,rx,ry,rz fixed.
    return NodalSupport(
        displacement_conditions={"X": ux, "Y": uy, "Z": FX},
        rotation_conditions={"X": FX, "Y": FX, "Z": FX})

def inner(th):
    return (AI * math.cos(th), BI * math.sin(th))
def outer(th):
    return (AO * math.cos(th), BO * math.sin(th))

def build(Nth, Ns):
    c = FERS()
    c.settings.analysis_options.order = AnalysisOrder.LINEAR
    mat = Material(name="LE1steel", e_mod=E, g_mod=G, density=7800, yield_stress=235e6)
    nd = {}
    for it in range(Nth + 1):
        th = (math.pi / 2) * it / Nth
        ix, iy = inner(th); ox, oy = outer(th)
        for js in range(Ns + 1):
            s = js / Ns
            x = (1 - s) * ix + s * ox
            y = (1 - s) * iy + s * oy
            # symmetry supports: left edge x=0 (it==Nth) -> ux=0; bottom y=0 (it==0) -> uy=0
            ux = FX if it == Nth else FR
            uy = FX if it == 0 else FR
            nd[(it, js)] = Node(X=x, Y=y, Z=0.0, nodal_support=_sup(ux, uy))
    for it in range(Nth):
        for js in range(Ns):
            n00, n10 = nd[(it, js)], nd[(it + 1, js)]
            n11, n01 = nd[(it + 1, js + 1)], nd[(it, js + 1)]
            c.add_plate(
                Plate(nodes=[n00, n10, n11], material=mat, thickness=T,
                      local_x_direction=(1, 0, 0), behavior="Membrane", plane_state="PlaneStress"),
                Plate(nodes=[n00, n11, n01], material=mat, thickness=T,
                      local_x_direction=(1, 0, 0), behavior="Membrane", plane_state="PlaneStress"))
    # Outward-normal edge traction on the outer arc (s=1, js=Ns), as equivalent nodal loads.
    lc = LoadCase(name="Edge")
    outer_nodes = [(it, nd[(it, Ns)]) for it in range(Nth + 1)]
    for k, (it, node) in enumerate(outer_nodes):
        th = (math.pi / 2) * it / Nth
        ox, oy = outer(th)
        # outward unit normal of ellipse x^2/AO^2 + y^2/BO^2 = 1  ->  grad (x/AO^2, y/BO^2)
        gx, gy = ox / AO**2, oy / BO**2
        gm = math.hypot(gx, gy); nxn, nyn = gx / gm, gy / gm
        # tributary arc length along the outer edge for this node
        def arclen(a, b):
            pa = outer((math.pi / 2) * a / Nth); pb = outer((math.pi / 2) * b / Nth)
            return math.hypot(pb[0] - pa[0], pb[1] - pa[1])
        trib = 0.0
        if it > 0: trib += 0.5 * arclen(it - 1, it)
        if it < Nth: trib += 0.5 * arclen(it, it + 1)
        force = P * T * trib   # [N]  (pressure * thickness * tributary length)
        NodalLoad(node=node, load_case=lc, magnitude=force, direction=(nxn, nyn, 0.0))
    c.add_load_case(lc)
    return c, nd

def sigma_yy_at_D(res, nd, Nth):
    """sigma_yy = ny/t on the plate nearest D=(2,0), i.e. near (it=0, js=0)."""
    pr = res["loadcases"]["Edge"]["plate_results"]
    best, bestd = None, 1e9
    for p in pr.values():
        cen = p["centroid"]; dx = cen["X"] - D_PT[0]; dy = cen["Y"] - D_PT[1]
        d = dx * dx + dy * dy
        if d < bestd:
            bestd, best = d, p
    return H.membrane_stress(best["resultants"]["ny"], T), best

def main():
    rows = []; last = None
    for (Nth, Ns) in [(12, 3), (24, 4), (48, 6), (72, 8)]:
        c, nd = build(Nth, Ns)
        res = H.static_results(c)
        s, _ = sigma_yy_at_D(res, nd, Nth)
        err = H.rel_err_pct(s, TARGET)
        rows.append((Nth, Ns, s, err))
        print(f"mesh {Nth}x{Ns:2d}  sigma_yy(D) = {s/1e6:8.4f} MPa  target 92.7  err {err:.2f}%")
        last = (Nth, Ns, c, s, err)
    conv = ", ".join(f"{a}x{b}:{e:.1f}%" for a, b, _, e in rows)
    matched = last[4] < 10.0
    print("convergence:", conv, " matched:", matched)
    Nth, Ns, c, s, err = last
    d = c.to_dict(include_results=False); d["results"] = None
    here = os.path.dirname(__file__)
    with open(os.path.join(here, "LE1.json"), "w") as fh:
        json.dump(d, fh)
    with open(os.path.join(here, "LE1_result.json"), "w") as fh:
        json.dump({"id": "LE1", "results": [{
            "quantity": "tangential edge stress sigma_yy at D=(2,0)",
            "target": TARGET, "fers": round(s, 1), "error_pct": round(err, 3),
            "unit": "Pa", "mesh_or_modes": f"{Nth}x{Ns} membrane"}],
            "convergence": conv, "matched": matched}, fh, indent=2)

if __name__ == "__main__":
    main()
