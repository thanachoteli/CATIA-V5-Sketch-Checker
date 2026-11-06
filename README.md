# CATIA Sketch Checker

A small [pycatia](https://github.com/evereux/pycatia) tool that lets an instructor export a **baseline** of sketch constraints from a correct CATIA V5 part, and lets students **compare their own part against it** and see exactly what is wrong.

It was built for a CAD course so that an instructor does not need to check every student's sketches by hand.

## How it works

1. The instructor opens the correct CATPart and exports a baseline (`.json` and `.csv`).
2. The instructor gives the `.json` file to the students.
3. A student opens their own CATPart and runs the check. The script reads every sketch and constraint in the active part and prints a report: pass or fail, a score, and a list of problems.

Constraints are compared by **type and value, not by name**. A student's constraints will have default names such as `Constraint.12`, so name-matching would flag everyone as wrong. Within each sketch, constraints are compared in any order.

## Requirements

- Windows with CATIA V5 installed and running
- Python 3.9 or newer (the script uses `str.removesuffix`)
- [pycatia](https://pypi.org/project/pycatia/)

```bash
pip install pycatia
```

## Usage

CATIA must be open with a **CATPart as the active document**.

### Instructor: create the baseline

```bash
python sketch_checker.py baseline
```

This writes `<PartName>_baseline.json` and `<PartName>_baseline.csv` next to the part. If the part has not been saved, they go to your Downloads folder. To choose the output location and name:

```bash
python sketch_checker.py baseline -o C:/course/plate_baseline
```

Distribute the `.json` file to students.

### Student: check your part

```bash
python sketch_checker.py check -b plate_baseline.json
```

- If `baseline.json` is in the same folder as the script, `-b` can be left out.
- A `.csv` baseline also works.
- The report is printed and saved as `<PartName>_check_report.txt` next to your part.

Optional: set the value tolerance (default `0.001`, in mm or degrees):

```bash
python sketch_checker.py check -b plate_baseline.json --tol 0.01
```

## Example report
The output report should be display in terminal and save as a text file.jk
```
======================================================================
SKETCH CHECK REPORT
======================================================================
Result : FAIL - see errors below.
Score  : 5/9 baseline constraints matched (55.6%)
Errors : 3    Warnings: 2
----------------------------------------------------------------------
[BAD] Sketch 'Plate_Profile_Z0': 2/4 constraints correct
  [ERROR] Wrong Length value: expected 220, found 200  (baseline item: Plate_Width)
  [ERROR] Missing Length = 160  (baseline item: Plate_Height)
[OK ] Sketch 'Boss_1_Bore_Z20': 3/3 constraints correct
  [WARN] Sketch is called 'Sketch.7' but should be called 'Boss_1_Bore_Z20'.
  [WARN] Extra Radius = 9 not in baseline  (yours: Constraint.9)
[BAD] Sketch 'Boss_2_Bore_Z20' NOT FOUND (2 constraints expected)
```

## What gets checked

| Finding | Level |
|---|---|
| Sketch from the baseline not found | Error |
| Constraint with the wrong value | Error |
| Constraint missing | Error |
| Constraint status other than `catCstStatusOK` (broken, inconsistent, ...) | Error |
| Sketch renamed (matched by similarity) | Warning |
| Extra constraint not in the baseline | Warning |
| Extra sketch not in the baseline | Warning |

**Result levels:** `PASS` means no errors and no warnings. `PASS with warnings` means no errors. `FAIL` means at least one error.

## Matching details

- **Sketches** are matched by name (case-insensitive). A baseline sketch with no name match is paired with the most similar unmatched student sketch, if at least 50% of their constraints overlap. That pairing is reported as a warning.
- **Constraints** inside a sketch are matched in two passes. First, exact matches (same type, value within tolerance). Then leftover constraints of the same type are paired by closest value and reported as "wrong value".
- Sketches are collected from solid bodies and from geometric sets, including nested ones.

## Baseline file format

```json
{
  "part_name": "Plate",
  "sketches": {
    "Plate_Profile_Z0": [
      { "name": "Plate_Width", "type": "catCstTypeLength",
        "status": "catCstStatusOK", "value": 220.0 }
    ]
  }
}
```

The CSV uses the columns `Sketch Name, Constraint Name, Type, Status, Value`.

## Limitations :(

- The check compares constraint **type and value only**. It cannot prove the geometry is in the right place. For example, a Distance of 50 could be measured from the wrong reference.
- `Distance` constraints do not record direction, so X and Y distances with the same value cannot be told apart.
- Only sketch constraints are checked. Features (pads, pockets), dimensions outside sketches, and parameters are not.

## Ideas for extension!
- Extract and compare actual geometry (circle centres, line endpoints).
- Batch mode: run the check on a folder of student parts and produce one summary table.
- Compare feature tree and feature parameters (pad lengths, pocket depths).

## License
idk
