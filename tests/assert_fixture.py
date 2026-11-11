"""Assert a known end-to-end result from the CI Spark fixture."""
import json
from pathlib import Path

out = Path("out/ci")
correct = json.loads((out / "reconciliation_corrected.json").read_text())
defect = json.loads((out / "reconciliation_defect.json").read_text())
profile = json.loads((out / "data_profile.json").read_text())
assert (correct["status"], correct["groups"]) == ("PASS", 5)
assert (defect["status"], defect["failed_groups"]) == ("FAIL", 3)
assert profile["status"] == "PASS"
group = next(row for row in defect["comparisons"]
             if (row["survey_year"], row["state_code"]) == (2023, 1))
assert group["expected"]["denominator"] == "40.00000000"
assert group["actual"]["denominator"] == "200.00000000"
assert set(group["failed_checks"]) == {"eligible", "denominator"}
