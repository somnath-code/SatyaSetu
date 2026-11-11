"""Assert the business rules and quarantine behavior on the real Spark output."""
import json
from pathlib import Path

from healthcare.cli import explain, lookup

out = Path("out/claims")
assert json.loads((out / "summary.json").read_text()) == {
    "PASS": 2, "QUARANTINED": 2, "REVIEW": 3,
}
c002 = explain(out, "C002")
assert set(c002["claim"]["review_reasons"]) == {"COVERAGE", "LATE_FILING", "HIGH_AMOUNT"}
assert {d["rule"] for d in c002["evidence"]} == set(c002["claim"]["review_reasons"])
for claim_id in ("C003", "C004"):
    assert lookup(out, claim_id)["review_reasons"] == ["REPEAT_ENCOUNTER"]
assert "MISSING_ENCOUNTER" in lookup(out, "C005")["quality_issues"]
assert "INVALID_AMOUNT" in lookup(out, "C006")["quality_issues"]
assert lookup(out, "C007")["status"] == "PASS"
