FERS Examples
=============

This folder contains runnable example scripts that demonstrate the features
of the FERS structural-analysis library.  Examples are grouped by number range:

  0xx  –  Basic Beam Validation Tests
  1xx  –  Visual / 3-D Rendering and Feature Examples
  2xx  –  Real-World Structural Application Examples
  8xx  –  Utility & Functionality Examples  (sections, I/O, cloud, DXF …)
  9xx  –  Experimental / Scratch


──────────────────────────────────────────────────────────────────
0xx – Basic Beam Validation Tests
──────────────────────────────────────────────────────────────────
001  Cantilever with End Load
002  Cantilever with Intermediate Load
003  Cantilever with Uniform Distributed Load
004  Cantilever with Partial Uniform Distributed Load
005  Cantilever with Triangular Distributed Load
006  Cantilever with Partial Triangular Distributed Load
007  Cantilever with End Moment

011  Simply Supported with Center Load
012  Simply Supported with Intermediate Load
013  Simply Supported with Double Symmetric Load
014  Simply Supported with Uniform Distributed Load

021  Simply Supported – Moment at Each Support
022  Simply Supported – Moment at Start Support
023  Simply Supported – Moment at Center

031  Fixed–Fixed with Center Load
032  Fixed–Fixed with Uniform Distributed Load

041  Rigid Member
042  Rigid Member (reversed)

051  Member Hinge at Half
052  Bending Moment Development
053  Bending Moment Development – Rigid Member

061  Tension Member

071  Support Connection

081  Double Cantilever
081  Double Cantilever – Out-of-Plane Load
082  Double Cantilever – Double Supported
083  Double Cantilever – Rope, Double Supported
084  Triple Cantilever in 3-D
085  Triple Cantilever in 3-D, Rotated −45° about Y

091  Load Combinations – Cantilever
093  Load Combinations – Hooked Cantilever


──────────────────────────────────────────────────────────────────
1xx – Visual / 3-D Rendering and Feature Examples
──────────────────────────────────────────────────────────────────
100  Unity Check – Beam Deflection (SLS) – chord-relative mid-span sag
                                    (MemberDeflection) against a span limit.
101  Unity Check – Reference Member Clearance – cross-member checks through
                                    reference_member.
101  Visual Cantilever with End Load
103  Visual Cantilever with Uniform Distributed Load
104  Visual Member Deflected Shape   – engine load-exact member_displacements vs
                                    client Hermite on a uniformly-loaded cantilever
                                    (set include_member_deflected_shape).
111  Visual Simply Supported with Center Load
121  Shear Deformation Toggle       – Euler-Bernoulli against Timoshenko on a
                                    cantilever.
122  Warping Deformation Toggle     – St. Venant against Vlasov torsion under an
                                    end torque.
131  Stiffness Curve – Cantilever   – a base spring whose rotational stiffness
                                    grows with the axial load.
132  Stiffness Curve – Sensitivity  – deflection against axial load, one model
                                    per load level.
141  Plate Surface Mesh             – a slab meshed automatically from its outline.
142  Plate Strip Surface Load       – a cantilevered plate strip under pressure,
                                    against the beam formula.
151  Seismic Response Spectrum      – a portal frame under an EN 1998-1 spectrum,
                                    by MRSA and by the lateral-force method; a
                                    roof beam's self-weight and mass set with
                                    weight_override.
181  Visual Double Cantilever
182  Visual Double Cantilever – Double Supported


──────────────────────────────────────────────────────────────────
2xx – Real-World Structural Application Examples
──────────────────────────────────────────────────────────────────
201  Simple Shed                  – 3-D gable portal-frame shed (6x8 m) with
                                    HEA140 columns, IPE160 rafters, IPE120 purlins,
                                    snow and wind load combinations (EN 1990/1991),
                                    saved to FERS Cloud.
202  Solar Rail                   – Ballasted flat-roof 2x2 solar panel mounting
                                    frame in aluminium RHS/SHS sections, with
                                    gravity, snow, and wind-uplift load combinations
                                    (EN 1990/1991), saved to FERS Cloud.
203  Premium Batch Solve          – Many models in one unattended run, with a
                                    bounded licence handshake and retry.


──────────────────────────────────────────────────────────────────
8xx – Utility & Functionality Examples
──────────────────────────────────────────────────────────────────
801  Section Library Lookup       – Use from_name() to pick standard steel
                                    sections (IPE, HEA, HEB, …) and inspect
                                    their properties.
802  Custom Section Factories     – Create sections from explicit dimensions
                                    using create_rhs, create_shs,
                                    create_angle_section, create_welded_i_section,
                                    create_cfs_c, create_cfs_z.
803  DXF Cross-Section Import     – Import an arbitrary cross-section from a
                                    DXF file via ShapePath.from_dxf().
804  Section Property Comparison  – Iterate over a series, find the lightest
                                    section that satisfies a deflection limit,
                                    and compare HEA/HEB/HEM families.
805  JSON Import / Export         – Round-trip a model through save_to_json(),
                                    from_json(), to_dict(), from_dict().
806  Cloud Save / Load            – Upload and retrieve models via FERS Cloud
                                    (requires an account and API key).
807  Custom Line Stroke           – Customise member visualisation stroke styles.
808  Default Materials            – Inspect and use the built-in material library.
809  Reading Results              – Node displacements, reactions and member
                                    forces; the read-only result tables and
                                    .copy(); save_to_json / from_json; solving
                                    straight to a file for large models.


──────────────────────────────────────────────────────────────────
9xx – Experimental / Scratch
──────────────────────────────────────────────────────────────────
901  Modular Visualization      – Demonstrates the modular renderer
                                    architecture (get_model_renderer,
                                    get_result_renderer).
922  Scratch Cantilever          – Quick playground / scratch file.
