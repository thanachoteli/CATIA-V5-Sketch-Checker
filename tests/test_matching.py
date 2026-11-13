from sketch_checker import compare_sketch, build_report

R = "catCstTypeRadius"
def c(name, v, t=R):
    return {"name": name, "type": t, "status": "catCstStatusOK", "value": v}

def test_named_identity():                      # professor's case
    r = compare_sketch([c("A", 3), c("B", 3)], [c("A", 4), c("B", 3)], 1e-3)
    (b, s, confirmed), = r["wrong"]
    assert (b["name"], s["name"], confirmed) == ("A", "A", True)
    assert r["matched"] == 1

def test_renamed_student_side_only():           # default names
    r = compare_sketch([c("A", 3), c("B", 3)],
                       [c("Constraint.1", 4), c("Constraint.2", 3)], 1e-3)
    (b, s, confirmed), = r["wrong"]
    assert s["name"] == "Constraint.1" and confirmed is False
    rep = build_report({"S": [c("A", 3), c("B", 3)]},
                       {"S": [c("Constraint.1", 4), c("Constraint.2", 3)]}, 1e-3)
    assert "'A'" not in rep and "'B'" not in rep and "expected" not in rep

def test_reversed_order_same_result():
    base = [c("A", 3), c("B", 3)]
    stud = [c("Constraint.1", 4), c("Constraint.2", 3)]
    r1 = compare_sketch(base, stud, 1e-3)
    r2 = compare_sketch(base[::-1], stud[::-1], 1e-3)
    assert [s["name"] for _, s, _ in r1["wrong"]] == \
           [s["name"] for _, s, _ in r2["wrong"]]

def test_two_unnamed_changes_are_ambiguous():
    r = compare_sketch([c("A", 3), c("B", 3)],
                       [c("Constraint.1", 4), c("Constraint.2", 5)], 1e-3)
    assert not r["wrong"] and len(r["ambiguous"]) == 1

def test_student_mode_hides_target_value():
    rep = build_report({"S": [c("Plate_Width", 220, "catCstTypeLength")]}, {"S": []}, 1e-3)
    assert "220" not in rep