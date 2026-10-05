"""Regenerate ``fers_core/sections/_british_steel_data.py`` from British Steel's datasheets.

The two PDFs are pinned by URL and SHA-256. A re-issued datasheet changes the hash
and stops this script, so new values only land after someone has looked at them.
The PDFs themselves are never committed.

Rows are written in the units the datasheets print them in, digit for digit, so the
generated module can be checked against the PDF by eye. The exceptions are the
misprints in ``_CORRECTIONS``, each listed with its evidence in the generated
``CORRECTIONS``. Conversion to SI happens in ``fers_core/sections/british_steel.py``.

Usage::

    python scripts/import_british_steel.py [--pdf-dir DIR]

``--pdf-dir`` reads ``uk.pdf`` / ``astm.pdf`` from DIR instead of downloading them.
Needs ``pypdf`` (requirements-dev.txt).
"""

from __future__ import annotations

import argparse
import hashlib
import math
import os
import re
import subprocess
import sys
import tempfile
import urllib.request

import pypdf

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_OUT = os.path.join(_ROOT, "fers_core", "sections", "_british_steel_data.py")

_DOCS = {
    "uk": (
        "https://www.britishsteel.co.uk/wp-content/uploads/2026/07/UK-sections-datasheets-20.07.26-1.pdf",
        "53cdfd1113f1956732f65cc11b23610b371fa81347aede19af1cb26c7fa64f49",
    ),
    "astm": (
        "https://www.britishsteel.co.uk/wp-content/uploads/2026/07/ASTM-datasheet-20.07.26-2.pdf",
        "c554a5ee27d4d5f17a4f60d32a69be428e66d7daba9ea747abc6b0c603c790d4",
    ),
}

# family -> (document, 0-based property pages, doc code printed in that document, expected rows)
# The UK PDF also carries UBP, ASB and angles; the ASTM PDF's pages 11-15 and 18 are
# fabrication tables (end clearance, notch, surface area), not section properties.
_FAMILIES = {
    "UB": ("uk", range(0, 8), "CUBD:ENG:072026", 134),
    "UC": ("uk", range(8, 12), "CUCD:ENG:072026", 62),
    "PFC": ("uk", range(14, 16), "CPFCD:ENG:072026", 12),
    "W": ("astm", range(0, 10), "CAWSD:ENG:072026", 186),
    "HP": ("astm", range(15, 17), "CAHSD:ENG:072026", 11),
}

# Column order of each generated row. The UK sheets label the major axis x-x, the
# ASTM sheets label it y-y (Eurocode letters), so both are mapped to major/minor here
# and never by letter.
_COLS_I = (
    "mass", "D", "B", "t", "T", "r", "d", "B_2T", "d_t",
    "I_major", "I_minor", "i_major", "i_minor",
    "Wel_major", "Wel_minor", "Wpl_major", "Wpl_minor",
    "u", "x", "H", "J", "A",
)  # fmt: skip
_COLS_PFC = (
    "mass", "D", "B", "t", "T", "Cy", "r", "d", "B_2T", "d_t",
    "I_major", "I_minor", "i_major", "i_minor",
    "Wel_major", "Wel_minor", "Wpl_major", "Wpl_minor",
    "u", "x", "H", "J", "A",
)  # fmt: skip
_COLS_ASTM = _COLS_I + ("w_lbft", "non_astm", "metric_designation")
_COLS_BY_FAMILY = {"UB": _COLS_I, "UC": _COLS_I, "PFC": _COLS_PFC, "W": _COLS_ASTM, "HP": _COLS_ASTM}

# Misprints in the datasheets, corrected here: name -> (corrected columns, evidence).
# Each was found by a row disagreeing with its own redundancy (mass vs A, i vs
# sqrt(I/A), Wel vs 2I/h, the meshed geometry, its twin on the other sheet). A web
# correction re-derives every property the web feeds; see _rederive.
_CORRECTIONS: dict[str, tuple[dict[str, str], str]] = {
    "UB 406x260x132": (
        {"t": "13.3"},
        "web printed 16.3 mm; the 132.52 kg/m mass needs 13.3 mm (W16X89, the same section, is 0.525 in), "
        "and A, I, W, J and H were computed from the misprint",
    ),
    "W16X89": (
        {"t": "13.3"},
        "the ASTM sheet's copy of UB 406x260x132, with the same misprinted 16.3 mm web",
    ),
    "W27X94": (
        {"t": "12.4"},
        "web printed 21.4 mm, digits swapped; the 140 kg/m mass needs 12.4 mm (W27X94 is 0.490 in), "
        "and A, I, W, J and H were computed from the misprint",
    ),
    "W16X100": (
        {"i_minor": "6.38"},
        "printed 2.38 cm; sqrt(I/A) and its twin UB 406x260x149 give 6.38",
    ),
    "W16X67": (
        {"I_minor": "4955"},
        "printed 4995 cm4; its twin UB 406x260x100, Wel = 2I/B and the section geometry give 4955",
    ),
}
_WEB_DEPENDENT = ("A", "I_major", "I_minor", "Wel_major", "Wel_minor", "Wpl_major", "Wpl_minor", "J", "H")

_NUM = r"-?\d+(?:\.\d+)?"
_UK_SERIAL = r"\d+ x \d+ x \d+(?:\.\d+)?"
_UK_A = re.compile(rf"^({_UK_SERIAL})\s+((?:{_NUM}\s+)*{_NUM})$")
_UK_B = re.compile(rf"^((?:{_NUM}\s+)*{_NUM})\s+({_UK_SERIAL})$")
_US_IMP = r"(W|HP) (\d+(?:\.\d+)?) x (\d+(?:\.\d+)?) (\d+(?:\.\d+)?)(\*?)"
# One metric designation is printed "W610 x 300 x 149", without the space.
_US_A = re.compile(rf"^{_US_IMP} ((?:W|HP) ?\d+ x \d+ x (\d+(?:\.\d+)?))\s+((?:{_NUM}\s+)*{_NUM})$")
_US_B = re.compile(rf"^((?:{_NUM}\s+)*{_NUM})\s+{_US_IMP}$")


def _fetch(doc: str, pdf_dir: str | None, tmp: str) -> str:
    url, sha = _DOCS[doc]
    path = os.path.join(pdf_dir or tmp, f"{doc}.pdf")
    if pdf_dir is None:
        urllib.request.urlretrieve(url, path)
    with open(path, "rb") as f:
        got = hashlib.sha256(f.read()).hexdigest()
    if got != sha:
        raise SystemExit(
            f"{doc}.pdf SHA-256 is {got}, pinned {sha}.\n"
            "British Steel re-issued the datasheet: review the changes, then update _DOCS."
        )
    return path


def _lines(reader: pypdf.PdfReader, pages: range) -> list[str]:
    text = "\n".join(reader.pages[i].extract_text() for i in pages)
    return [ln.strip() for ln in text.splitlines()]


def _uk_family(family: str, lines: list[str]) -> dict[str, tuple]:
    a: dict[str, list[str]] = {}
    b: dict[str, list[str]] = {}
    for ln in lines:
        m = _UK_A.match(ln)
        if m and len(m.group(2).split()) >= 13:
            a[m.group(1)] = m.group(2).split()
            continue
        m = _UK_B.match(ln)
        if m and len(m.group(1).split()) >= 9:
            serial = m.group(2)
            # British Steel prints this series as 406 x 260 on the dimensions page
            # and 410 x 260 on the properties page; 406 is the designation.
            if family == "UB" and serial.startswith("410 x 260 x "):
                serial = "406" + serial[3:]
            b[serial] = m.group(1).split()
    if set(a) != set(b):
        raise SystemExit(f"{family}: pages do not pair up: {sorted(set(a) ^ set(b))}")

    rows: dict[str, tuple] = {}
    for serial, pa in a.items():
        pb = b[serial]
        if family == "PFC":
            if len(pa) != 13 or len(pb) != 10:
                raise SystemExit(f"PFC {serial}: expected 13 + 10 values, got {len(pa)} + {len(pb)}")
            vals = pa + pb  # page A ends with ix, page B starts with iy
        else:
            if len(pa) != 13 or len(pb) != 9:
                raise SystemExit(f"{family} {serial}: expected 13 + 9 values, got {len(pa)} + {len(pb)}")
            vals = pa + pb
        rows[f"{family} {serial.replace(' ', '')}"] = tuple(vals)
    return rows


def _us_name(fam: str, depth: str, width: str, lbft: str, star: str) -> str:
    # A starred row is a non-ASTM weight that has no standard W designation, and
    # two of them share depth and lb/ft with a real one: "W 18 x 6 50*" next to
    # W18X50 (= W 18 x 7.5 50). Keep the nominal width in their names.
    return f"{fam}{depth}X{width}X{lbft}" if star else f"{fam}{depth}X{lbft}"


def _us_family(family: str, lines: list[str]) -> dict[str, tuple]:
    a: dict[str, tuple] = {}
    b: dict[str, list[str]] = {}
    for ln in lines:
        m = _US_A.match(ln)
        if m and m.group(1) == family:
            fam, depth, width, lbft, star, metric, mass, rest = m.groups()
            metric = re.sub(r"^(W|HP)(?=\d)", r"\1 ", metric)
            name = _us_name(fam, depth, width, lbft, star)
            if name in a:
                raise SystemExit(f"{name}: printed twice")
            a[name] = (lbft, star == "*", metric, mass, rest.split())
            continue
        m = _US_B.match(ln)
        if m and m.group(2) == family:
            nums, fam, depth, width, lbft, star = m.groups()
            b[_us_name(fam, depth, width, lbft, star)] = nums.split()
    if set(a) != set(b):
        raise SystemExit(f"{family}: pages do not pair up: {sorted(set(a) ^ set(b))}")

    rows: dict[str, tuple] = {}
    for name, (lbft, non_astm, metric, mass, pa) in a.items():
        pb = b[name]
        if len(pa) != 10 or len(pb) != 11:
            raise SystemExit(f"{name}: expected 10 + 11 values, got {len(pa)} + {len(pb)}")
        # page A: h b tw tf r d B/2T d/t Iy Iz; page B: iy iz Wely Welz Wply Wplz u x H J A
        rows[name] = (mass, *pa[:10], *pb[:2], *pb[2:6], *pb[6:11], lbft, non_astm, metric)
    return rows


def _meshed(family: str, row: dict) -> dict[str, float]:
    sys.path.insert(0, _ROOT)
    from fers_core import Material
    from fers_core.members.section import Section

    steel = Material(name="S235", e_mod=210e9, g_mod=81e9, density=7850, yield_stress=235e6)
    factory = Section.create_u_section if family == "PFC" else Section.create_ipe_section
    mm = {k: float(row[k]) / 1e3 for k in ("D", "B", "t", "T", "r")}
    s = factory(name="check", material=steel, h=mm["D"], b=mm["B"], t_w=mm["t"], t_f=mm["T"], r=mm["r"])
    return {
        "A": s.area,
        "I_major": s.i_z,
        "I_minor": s.i_y,
        "Wel_major": s.wel_z,
        "Wel_minor": s.wel_y,
        "Wpl_major": s.wpl_z,
        "Wpl_minor": s.wpl_y,
        "J": s.j,
        "H": s.i_w,
    }


def _fmt(value: float, like: str) -> str:
    """``value`` printed to as many decimals as the datasheet printed ``like``."""
    decimals = len(like.split(".")[1]) if "." in like else 0
    return f"{value:.{decimals}f}"


def _rederive(family: str, printed: dict, fixed: dict) -> None:
    """Re-derive what a misprinted web fed into, in place on ``fixed``.

    Each property is scaled by meshed(correct) / meshed(misprinted) rather than
    replaced by the mesh, so British Steel's own conventions (their warping formula,
    their fillets) survive and only the misprint's effect is taken out.
    """
    old, new = _meshed(family, printed), _meshed(family, fixed)
    for k in _WEB_DEPENDENT:
        fixed[k] = _fmt(float(printed[k]) * new[k] / old[k], printed[k])
    area = float(fixed["A"])
    for axis in ("major", "minor"):
        fixed[f"i_{axis}"] = _fmt(math.sqrt(float(fixed[f"I_{axis}"]) / area), printed[f"i_{axis}"])
    fixed["d_t"] = _fmt(float(fixed["d"]) / float(fixed["t"]), printed["d_t"])
    # Buckling parameter u and torsional index x as the UK tables define them, with
    # h_s = D - T the distance between flange centroids (cm).
    h_s = (float(fixed["D"]) - float(fixed["T"])) / 10
    gamma = 1 - float(fixed["I_minor"]) / float(fixed["I_major"])
    wpl = float(fixed["Wpl_major"])
    fixed["u"] = _fmt((4 * wpl**2 * gamma / (area**2 * h_s**2)) ** 0.25, printed["u"])
    fixed["x"] = _fmt(0.566 * h_s * math.sqrt(area / float(fixed["J"])), printed["x"])


def _apply_corrections(tables: dict[str, dict[str, tuple]]) -> dict[str, tuple[str, dict]]:
    applied: dict[str, tuple[str, dict]] = {}
    for name, (fixes, why) in _CORRECTIONS.items():
        family = next(f for f, rows in tables.items() if name in rows)
        cols = _COLS_BY_FAMILY[family]
        printed = dict(zip(cols, tables[family][name]))
        stale = [c for c, v in fixes.items() if printed[c] == v]
        if stale:
            raise SystemExit(f"{name}: {stale} already print the corrected value; review _CORRECTIONS")
        fixed = {**printed, **fixes}
        if "t" in fixes:
            _rederive(family, printed, fixed)
        tables[family][name] = tuple(fixed[c] for c in cols)
        applied[name] = (why, {c: (printed[c], fixed[c]) for c in cols if fixed[c] != printed[c]})
    return applied


def _literal(v) -> str:
    if isinstance(v, bool):
        return repr(v)
    if isinstance(v, str) and re.fullmatch(_NUM, v):
        return v if "." in v else v + ".0"
    return repr(v)


def _render(tables: dict[str, dict[str, tuple]], corrections: dict[str, tuple[str, dict]]) -> str:
    out = [
        "# ruff: noqa: E501",
        "# Section data: British Steel. Attribution and terms: https://ferscloud.com/legal-notice/imprint",
        "# Generated by scripts/import_british_steel.py from the pinned British Steel datasheets.",
        "# Do not edit by hand: re-run the script.",
        '"""British Steel section tables, as printed (mm, cm, cm2, cm3, cm4, dm6, kg/m, lb/ft),',
        "except the datasheet misprints listed in ``CORRECTIONS``.",
        "",
        "Each row follows the matching ``COLS_*`` tuple. ``*_major`` is the strong axis,",
        'whatever letter the datasheet uses for it."""',
        "",
        f"COLS_I = {_COLS_I!r}",
        f"COLS_PFC = {_COLS_PFC!r}",
        f"COLS_ASTM = {_COLS_ASTM!r}",
        "",
        "# name -> (evidence, {column: (printed, corrected)})",
        "CORRECTIONS: dict[str, tuple[str, dict[str, tuple[float, float]]]] = {",
    ]
    for name, (why, changes) in corrections.items():
        pairs = ", ".join(f"{c!r}: ({_literal(a)}, {_literal(b)})" for c, (a, b) in changes.items())
        out.append(f"    {name!r}: ({why!r}, {{{pairs}}}),")
    out += ["}", "", "# fmt: off"]
    for family, rows in tables.items():
        out.append(f"{family}: dict[str, tuple] = {{")
        for name, row in rows.items():
            out.append(f"    {name!r}: ({', '.join(_literal(v) for v in row)}),")
        out.append("}")
        out.append("")
    out.append("# fmt: on")
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pdf-dir", help="read uk.pdf / astm.pdf from here instead of downloading")
    args = ap.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        readers = {doc: pypdf.PdfReader(_fetch(doc, args.pdf_dir, tmp)) for doc in _DOCS}
        texts = {doc: "\n".join(p.extract_text() for p in r.pages) for doc, r in readers.items()}
        tables: dict[str, dict[str, tuple]] = {}
        for family, (doc, pages, code, count) in _FAMILIES.items():
            if code not in texts[doc]:
                raise SystemExit(f"{family}: doc code {code} not found in {doc}.pdf")
            lines = _lines(readers[doc], pages)
            rows = _uk_family(family, lines) if doc == "uk" else _us_family(family, lines)
            if len(rows) != count:
                raise SystemExit(f"{family}: parsed {len(rows)} rows, expected {count}")
            tables[family] = rows

    corrections = _apply_corrections(tables)
    with open(_OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(_render(tables, corrections))
    subprocess.run([sys.executable, "-m", "ruff", "format", _OUT], check=False)
    print(f"wrote {sum(len(t) for t in tables.values())} sections to {os.path.relpath(_OUT, _ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
