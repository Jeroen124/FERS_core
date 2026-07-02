"""NAFEMS LE5 — Z-section cantilever under end torque, via FERS's 7-DOF warping beam.

The reference is a thin-walled open Z-section solved as a folded shell; the -108 MPa axial
stress at the flange tip is a RESTRAINED-WARPING (Vlasov) stress. The published research spec
marked this "infeasible" assuming a 6-DOF beam — but FERS has a 7th warping DOF and a warping
constant input, so we model the whole section as ONE beam member and recover the warping normal
stress from the bimoment:  sigma_w = B * omega_n / C_w.

Z-section (mid-surface, t=0.1 m): web at Z=0, Y in [-1,1]; lower flange Y=-1, Z in [-1,0];
upper flange Y=+1, Z in [0,1]. Point-symmetric => shear centre = centroid = origin.
  A = 0.4,  I_y = 0.06667,  I_z = 0.26667,  I_yz = 0.10,  J = 1.333e-3,  C_w = 0.041667 m^6
  omega_n at a flange tip = +0.75 m^2   (normalized sectorial coordinate)
Material E=210 GPa, nu=0.3, G=80.769 GPa. Length 10 m; fully clamped (incl. warping) at X=0;
end torque T = 1.2 MN.m about X. Target: sigma_xx = -108 MPa at A=(2.5,-1,-1) (flange tip).
"""
import sys, os, json, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import nafems_harness as H
from fers_core import (FERS, Node, Member, MemberSet, NodalSupport, Material, Section,
                       AnalysisOrder, SupportCondition)
from fers_core.loads.nodalmoment import NodalMoment

E, NU, RHO = 210e9, 0.3, 7800.0
G = E / (2 * (1 + NU))
L = 10.0
T_TORQUE = 1.2e6           # N.m
CW = 0.0416667             # warping constant [m^6]
OMEGA_TIP = 0.75           # normalized sectorial coordinate at flange tip [m^2]
X_A = 2.5
TARGET = -108e6

SEC = dict(area=0.4, i_y=0.0666667, i_z=0.2666667, j=1.3333e-3, i_w=CW, i_yz=0.10, y_s=0.0, z_s=0.0)

FX, FR = SupportCondition.fixed(), SupportCondition.free()

def build(n_el=4):
    c = FERS()
    c.settings.analysis_options.order = AnalysisOrder.LINEAR
    mat = Material(name="LE5steel", e_mod=E, g_mod=G, density=RHO, yield_stress=235e6)
    sec = Section(name="Zsec", material=mat, **SEC)
    xs = [L * i / n_el for i in range(n_el + 1)]   # nodes incl. one at 2.5 when n_el=4
    nodes = [Node(x, 0.0, 0.0) for x in xs]
    nodes[0].nodal_support = NodalSupport(
        displacement_conditions={"X": FX, "Y": FX, "Z": FX},
        rotation_conditions={"X": FX, "Y": FX, "Z": FX},
        warping_condition=FX)   # restrained warping at the clamped end
    c.add_member_set(MemberSet(members=[
        Member(start_node=nodes[i], end_node=nodes[i + 1], section=sec) for i in range(n_el)]))
    lc = c.create_load_case(name="Torque")
    NodalMoment(node=nodes[-1], load_case=lc, magnitude=T_TORQUE, direction=(1.0, 0.0, 0.0))
    return c, nodes

def bw_at_x25(res):
    """Bimoment at x=2.5: member 1 ends there and member 2 starts there (n_el=4)."""
    mr = res["loadcases"]["Torque"]["member_results"]
    bw_end_m1 = mr["1"]["end_node_forces"]["bw"]
    bw_start_m2 = mr["2"]["start_node_forces"]["bw"]
    return bw_end_m1, bw_start_m2

def main():
    c, nodes = build(4)
    res = H.static_results(c)
    lam = math.sqrt(G * SEC["j"] / (E * CW))
    phi2 = (T_TORQUE * lam / (G * SEC["j"])) * (math.tanh(lam * L) * math.cosh(lam * X_A) - math.sinh(lam * X_A))
    B_analytical = -E * CW * phi2
    sig_analytical = E * OMEGA_TIP * phi2
    print(f"analytical (Vlasov): B(2.5)={B_analytical:.4e}  sigma_tip={sig_analytical/1e6:.2f} MPa")

    bw1, bw2 = bw_at_x25(res)
    bw = 0.5 * (abs(bw1) + abs(bw2))
    sigma = bw * OMEGA_TIP / CW
    err_target = H.rel_err_pct(sigma, abs(TARGET))
    err_vlasov = H.rel_err_pct(sigma, abs(sig_analytical))
    print(f"FERS bimoment at x=2.5: {bw1:.4e} (m1 end) / {bw2:.4e} (m2 start)")
    print(f"FERS warping stress at flange tip A = {sigma/1e6:.3f} MPa")
    print(f"  vs NAFEMS -108 MPa: err {err_target:.2f}%   vs Vlasov {sig_analytical/1e6:.2f} MPa: err {err_vlasov:.2f}%")

    d = c.to_dict(include_results=False)
    d["results"] = None
    here = os.path.dirname(__file__)
    with open(os.path.join(here, "LE5.json"), "w") as fh:
        json.dump(d, fh)
    with open(os.path.join(here, "LE5_result.json"), "w") as fh:
        json.dump({"id": "LE5", "results": [{
            "quantity": "axial warping stress sigma_xx at flange tip A (x=2.5 m), via 7-DOF warping beam",
            "target": TARGET, "fers": -round(sigma, 1), "error_pct": round(err_target, 3),
            "unit": "Pa", "mesh_or_modes": "1 warping beam, 4 elements"}],
            "matched": err_target < 3.0,
            "method": "Vlasov restrained-warping torsion; sigma = bimoment * omega_n / C_w"}, fh, indent=2)

if __name__ == "__main__":
    main()

if __name__ == "__main__":
    main()
