"""
CATIA Sketch Checker (pycatia)
==============================
Two modes:

  1) INSTRUCTOR - build the baseline from the correct part (active CATPart):
         python sketch_checker.py baseline
     -> writes <PartName>_baseline.json and .csv next to the part.
        Give the .json file to the students.

  2) STUDENT - check own part against the instructor's baseline:
         python sketch_checker.py check -b path/to/baseline.json
     -> prints a report and saves <PartName>_check_report.txt

Matching is deliberately NAME-INDEPENDENT at the constraint level, because
students will have default names such as "Constraint.12". Within each sketch
constraints are compared by (type, value). Sketches are matched by name; if a
student renamed a sketch, it is matched to the most similar unmatched one.
"""

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

# Constraint types that carry a dimension value (compared by enum name)
DIMENSIONAL_TYPES = {
    "catCstTypeDistance", "catCstTypeLength", "catCstTypeAngle",
    "catCstTypePlanarAngle", "catCstTypeRadius", "catCstTypeMajorRadius",
    "catCstTypeMinorRadius", "catCstTypeCylinderRadius",
}

# Types that are treated as the SAME when comparing. Edit to suit the course.
# Left side = type found, right side = type it is treated as.
# Horizontal / vertical are orientation constraints, and the CATIA sketcher
# creates them automatically when a student draws with the Rectangle tool.
EQUIVALENT_TYPES = {
    "catCstTypeHorizontality": "catCstTypeParallelism",
    "catCstTypeVerticality": "catCstTypeParallelism",
    # Uncomment to accept Length and Distance as interchangeable dimensions:
    # "catCstTypeLength": "catCstTypeDistance",
}

# Friendlier names for the report
FRIENDLY_TYPES = {
    "catCstTypeOn": "Coincidence / point-on",
    "catCstTypeParallelism": "Parallelism (incl. horizontal/vertical)",
    "catCstTypeDistance": "Distance",
    "catCstTypeLength": "Length",
    "catCstTypeRadius": "Radius",
    "catCstTypeAngle": "Angle",
}

DEFAULT_TOL = 1e-3          # mm (or deg for angles)
SIMILARITY_MIN = 0.5        # min similarity to match a renamed sketch


def canon(type_name):
    """Type name used for comparing (applies EQUIVALENT_TYPES)."""
    return EQUIVALENT_TYPES.get(type_name, type_name)


# ----------------------------------------------------------------------------
# CATIA extraction
# ----------------------------------------------------------------------------
def collect_sketches(hybrid_body, sketch_list):
    """Recursively collect sketches from a geometric set and nested sets."""
    try:
        hb_sketches = hybrid_body.hybrid_sketches
        for i in range(hb_sketches.count):
            sketch_list.append(hb_sketches.item(i + 1))
    except Exception:
        pass
    try:
        sub_bodies = hybrid_body.hybrid_bodies
        for i in range(sub_bodies.count):
            collect_sketches(sub_bodies.item(i + 1), sketch_list)
    except Exception:
        pass


def get_active_part():
    """Return (part_document, part) or exit if no CATPart is active."""
    from pycatia import catia
    from pycatia.mec_mod_interfaces.part_document import PartDocument

    try:
        caa = catia()
        active_doc = caa.active_document
    except Exception as e:
        sys.exit(f"Could not connect to CATIA. Is it running with a part "
                 f"open?\n({e})")
    if type(active_doc) is not PartDocument:
        sys.exit("A CATPart document must be the active document.")
    return active_doc, active_doc.part


def extract_part_sketches():
    """Read every sketch/constraint of the active part.

    Returns (doc_name, doc_dir, {sketch_name: [constraint dicts]}).
    """
    from pycatia.enumeration.enums import CatConstraintType, CatConstraintStatus

    part_document, part = get_active_part()

    doc_name = part_document.name.removesuffix(".CATPart")
    doc_path_str = str(part_document.path())
    if doc_path_str == part_document.name:           # unsaved document
        doc_dir = Path.home() / "Downloads"
    else:
        doc_dir = Path(doc_path_str).parent

    all_sketches = []
    for b_idx in range(part.bodies.count):
        try:
            body_sketches = part.bodies.item(b_idx + 1).sketches
            for s_idx in range(body_sketches.count):
                all_sketches.append(body_sketches.item(s_idx + 1))
        except Exception:
            pass
    for hb_idx in range(part.hybrid_bodies.count):
        collect_sketches(part.hybrid_bodies.item(hb_idx + 1), all_sketches)

    result = {}
    for sketch in all_sketches:
        name = sketch.name
        if name in result:                            # duplicate sketch names
            n = 2
            while f"{name} ({n})" in result:
                n += 1
            name = f"{name} ({n})"
        result[name] = []

        try:
            constraints = sketch.constraints
        except Exception:
            continue

        for c_idx in range(constraints.count):
            try:
                c = constraints.item(c_idx + 1)
                try:
                    type_str = CatConstraintType(c.type).name
                except ValueError:
                    type_str = f"unknown_{c.type}"
                try:
                    status_str = CatConstraintStatus(c.status).name
                except ValueError:
                    status_str = f"unknown_{c.status}"

                value = None
                if type_str in DIMENSIONAL_TYPES:
                    try:
                        value = round(float(c.dimension.value), 6)
                    except Exception:
                        value = None
                result[name].append({
                    "name": c.name, "type": type_str,
                    "status": status_str, "value": value,
                })
            except Exception as e:
                print(f"  Warning: could not read constraint {c_idx + 1} "
                      f"in '{name}': {e}")

    return doc_name, doc_dir, result


# ----------------------------------------------------------------------------
# Baseline I/O
# ----------------------------------------------------------------------------
def save_baseline(out_dir, stem, part_name, sketches):
    """Write <stem>.json and <stem>.csv into out_dir."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{stem}.json"
    csv_path = out_dir / f"{stem}.csv"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"part_name": part_name, "sketches": sketches}, f, indent=2)

    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, quoting=csv.QUOTE_ALL)
        w.writerow(["Sketch Name", "Constraint Name", "Type", "Status", "Value"])
        for sk, cs in sketches.items():
            for c in cs:
                w.writerow([sk, c["name"], c["type"], c["status"],
                            "" if c["value"] is None else c["value"]])
    return json_path, csv_path


def load_baseline(path):
    """Load baseline from .json (preferred) or the .csv exported earlier."""
    path = Path(path)
    if not path.exists():
        sys.exit(f"Baseline file not found: {path}")

    try:
        if path.suffix.lower() == ".json":
            with open(path, encoding="utf-8") as f:
                return json.load(f)["sketches"]

        sketches = {}
        with open(path, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                val = row["Value"].strip()
                sketches.setdefault(row["Sketch Name"], []).append({
                    "name": row["Constraint Name"], "type": row["Type"],
                    "status": row["Status"],
                    "value": float(val) if val else None,
                })
        return sketches
    except (KeyError, ValueError, json.JSONDecodeError) as e:
        sys.exit(f"Baseline file is not valid ({path.name}): {e!r}")


def find_default_baseline():
    here = Path(__file__).resolve().parent
    exact = here / "baseline.json"
    if exact.exists():
        return exact
    found = sorted(here.glob("*_baseline.json"))
    if len(found) == 1:
        return found[0]
    if len(found) > 1:
        sys.exit("Several *_baseline.json files found next to the script. "
                 "Choose one with -b path/to/file.json")
    sys.exit("No baseline found next to the script. "
             "Use -b path/to/baseline.json")


# ----------------------------------------------------------------------------
# Comparison (pure Python - no CATIA needed)
# ----------------------------------------------------------------------------
def _same_value(a, b, tol):
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return abs(a - b) <= tol


def _signature(constraints):
    return Counter((canon(c["type"]),
                    None if c["value"] is None else round(c["value"], 3))
                   for c in constraints)


def _similarity(a, b):
    sa, sb = _signature(a), _signature(b)
    union = sum((sa | sb).values())
    return sum((sa & sb).values()) / union if union else 0.0


def compare_sketch(base, stud, tol):
    """Compare one sketch. Returns dict describing the differences."""
    b_left = list(range(len(base)))
    s_left = list(range(len(stud)))
    matched = 0

    # Pass 1: exact matches (same type, same value within tolerance)
    for bi in b_left[:]:
        for si in s_left:
            if (canon(base[bi]["type"]) == canon(stud[si]["type"])
                    and _same_value(base[bi]["value"], stud[si]["value"], tol)):
                b_left.remove(bi)
                s_left.remove(si)
                matched += 1
                break

    # Pass 2: same type but wrong value -> pair up closest values
    wrong = []
    for bi in b_left[:]:
        if base[bi]["value"] is None:
            continue
        cands = [si for si in s_left
                 if canon(stud[si]["type"]) == canon(base[bi]["type"])
                 and stud[si]["value"] is not None]
        if cands:
            si = min(cands, key=lambda k: abs(stud[k]["value"] - base[bi]["value"]))
            wrong.append((base[bi], stud[si]))
            b_left.remove(bi)
            s_left.remove(si)

    return {
        "matched": matched,
        "wrong": wrong,
        "missing": [base[i] for i in b_left],
        "extra": [stud[i] for i in s_left],
        "bad_status": [c for c in stud if c["status"] != "catCstStatusOK"],
    }


def _label(t):
    return FRIENDLY_TYPES.get(t, t.replace("catCstType", ""))


def _fmt(v):
    return ("%.4f" % v).rstrip("0").rstrip(".")


def build_report(baseline, student, tol):
    lines, errors, warnings = [], 0, 0
    total_base = sum(len(v) for v in baseline.values())
    total_ok = 0

    # --- match sketches by name first
    norm = lambda s: s.strip().lower()
    stud_by_norm = {norm(k): k for k in student}
    pairs, base_unmatched = [], []
    for bname in baseline:
        sname = stud_by_norm.pop(norm(bname), None)
        if sname is not None:
            pairs.append((bname, sname, False))
        else:
            base_unmatched.append(bname)
    stud_unmatched = list(stud_by_norm.values())

    # --- then pair renamed sketches, best similarity first
    cands = sorted(((_similarity(baseline[b], student[s]), b, s)
                    for b in base_unmatched for s in stud_unmatched),
                   key=lambda t: t[0], reverse=True)
    for score, bname, sname in cands:
        if score < SIMILARITY_MIN:
            break
        if bname in base_unmatched and sname in stud_unmatched:
            pairs.append((bname, sname, True))
            base_unmatched.remove(bname)
            stud_unmatched.remove(sname)

    order = {b: i for i, b in enumerate(baseline)}
    pairs.sort(key=lambda p: order[p[0]])

    # --- per-sketch comparison
    for bname, sname, renamed in pairs:
        r = compare_sketch(baseline[bname], student[sname], tol)
        total_ok += r["matched"]
        problems = []

        if renamed:
            warnings += 1
            problems.append(f"  [WARN] Sketch is called '{sname}' but should be "
                            f"called '{bname}'.")
        for b, s in r["wrong"]:
            errors += 1
            problems.append(f"  [ERROR] Wrong {_label(b['type'])} value: expected "
                            f"{_fmt(b['value'])}, found {_fmt(s['value'])}  "
                            f"(baseline item: {b['name']})")
        for b in r["missing"]:
            errors += 1
            v = f" = {_fmt(b['value'])}" if b["value"] is not None else ""
            problems.append(f"  [ERROR] Missing {_label(b['type'])}{v}  "
                            f"(baseline item: {b['name']})")
        for s in r["extra"]:
            warnings += 1
            v = f" = {_fmt(s['value'])}" if s["value"] is not None else ""
            problems.append(f"  [WARN] Extra {_label(s['type'])}{v} not in "
                            f"baseline  (yours: {s['name']})")
        for s in r["bad_status"]:
            errors += 1
            problems.append(f"  [ERROR] Constraint '{s['name']}' has status "
                            f"{s['status']} (broken/inconsistent?)")

        n_base = len(baseline[bname])
        tag = "OK " if not any("[ERROR]" in p for p in problems) else "BAD"
        lines.append(f"[{tag}] Sketch '{bname}': {r['matched']}/{n_base} "
                     f"constraints correct")
        lines.extend(problems)

    for bname in base_unmatched:
        errors += 1
        lines.append(f"[BAD] Sketch '{bname}' NOT FOUND "
                     f"({len(baseline[bname])} constraints expected)")
    for sname in stud_unmatched:
        warnings += 1
        lines.append(f"[WARN] Extra sketch '{sname}' not in the baseline.")

    # --- header / verdict
    pct = 100.0 * total_ok / total_base if total_base else 0.0
    if errors == 0 and warnings == 0:
        verdict = "PASS - sketches match the baseline."
    elif errors == 0:
        verdict = "PASS with warnings - review the warnings below."
    else:
        verdict = "FAIL - see errors below."

    header = [
        "=" * 70,
        "SKETCH CHECK REPORT",
        "=" * 70,
        f"Result : {verdict}",
        f"Score  : {total_ok}/{total_base} baseline constraints matched "
        f"({pct:.1f}%)",
        f"Errors : {errors}    Warnings: {warnings}",
        "-" * 70,
    ]
    return "\n".join(header + lines) + "\n"


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------
def cmd_baseline(args):
    doc_name, doc_dir, sketches = extract_part_sketches()
    n = sum(len(v) for v in sketches.values())
    if n == 0:
        sys.exit("No sketch constraints found in the active part - "
                 "baseline not written.")

    if args.output:
        out = Path(args.output)
        if out.suffix.lower() in (".json", ".csv"):
            out = out.with_suffix("")
        out_dir, stem = out.parent, out.name       # used exactly as given
    else:
        out_dir, stem = doc_dir, f"{doc_name}_baseline"

    print(f"\nFound {len(sketches)} sketch(es), {n} constraint(s)")
    json_path, csv_path = save_baseline(out_dir, stem, doc_name, sketches)
    print(f"Baseline saved:\n  {json_path}\n  {csv_path}")


def cmd_check(args):
    baseline = load_baseline(args.baseline or find_default_baseline())
    doc_name, doc_dir, student = extract_part_sketches()
    report = build_report(baseline, student, args.tol)
    print("\n" + report)
    out = doc_dir / f"{doc_name}_check_report.txt"
    try:
        out.write_text(report, encoding="utf-8")
        print(f"Report saved to: {out}")
    except OSError as e:
        print(f"Could not save report: {e}")


def main():
    p = argparse.ArgumentParser(description="CATIA sketch baseline/checker")
    sub = p.add_subparsers(dest="mode", required=True)

    pb = sub.add_parser("baseline", help="(instructor) export baseline")
    pb.add_argument("-o", "--output",
                    help="output path without extension, e.g. C:/x/plate_baseline "
                         "(default: <PartName>_baseline next to the part)")
    pb.set_defaults(func=cmd_baseline)

    pc = sub.add_parser("check", help="(student) compare with baseline")
    pc.add_argument("-b", "--baseline",
                    help="baseline .json or .csv (default: baseline.json or the "
                         "single *_baseline.json next to this script)")
    pc.add_argument("--tol", type=float, default=DEFAULT_TOL,
                    help=f"value tolerance (default {DEFAULT_TOL})")
    pc.set_defaults(func=cmd_check)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()