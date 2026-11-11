"""Save evidence in machine-readable JSON and human-readable Markdown."""

import json
from decimal import Decimal
from pathlib import Path


def json_value(value):
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"Cannot serialize {type(value).__name__}")


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, default=json_value, indent=2) + "\n", encoding="utf-8")


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def migration_report(path, assessment, correct, defect, diff, tickets, snippets, scope):
    failed = [row for row in defect["comparisons"] if row["failed_checks"]]
    outcome = "PASS" if (
        assessment["verdict"] == "SUITABLE" and assessment["validation_status"] == "PASS" and failed
    ) else "INVESTIGATE"
    lines = [
        "# BRFSS migration comparison", "",
        f"Input scope: {scope}",
        f"Design verdict: **{assessment['verdict']}**",
        f"Validation verdict: **{assessment['validation_status']}**. "
        f"Metric parity: **{correct['status']}** for {correct['groups']} geography/year groups.",
        f"Defect scenario: **{defect['status']}**, with {len(failed)} mismatched groups.",
        f"End-to-end demo outcome: **{outcome}**.", "",
        "## Architecture and model comparison", "",
        "| Concern | Simulated legacy | Target |",
        "|---|---|---|",
        "| Ingestion | Annual flat file | PySpark staging with source year and row lineage |",
        "| Grain | One row per survey interview | One survey fact row per input interview |",
        "| Keys | Year + input row position | Same composite lineage key for snapshot reconciliation |",
        "| Model | Survey fields in one wide table | Narrow fact with year and geography dimensions |",
        "| Report | Reference calculation by year and geography | Gold weighted metric with numerator and denominator |",
        "| Evidence | Baseline built from staged source rows | Counts, weights, eligibility and totals compared at the same grain |",
        "", "See [data_profile.json](data_profile.json) for both profiles and "
        "[reconciliation_corrected.json](reconciliation_corrected.json) for group details.",
        "", "## Example mismatch", "",
    ]
    if failed:
        row = failed[0]
        lines += [
            f"Year {row['survey_year']}, geography {row['state_code']}.",
            f"Expected denominator {row['expected']['denominator']}, "
            f"actual denominator {row['actual']['denominator']}.",
            f"Failed checks: {', '.join(row['failed_checks'])}.",
            "The defective calculation includes codes 7 and 9 in the eligible responses.",
        ]
    else:
        lines.append("No defect was observable in this input slice. Use more rows or the bundled fixture.")
    if diff:
        lines += ["", "## Survey-year schema comparison", "",
                  f"{diff['from_year']}: {diff['from_field_count']} fields. "
                  f"{diff['to_year']}: {diff['to_field_count']} fields.",
                  f"Added {len(diff['added'])}, removed {len(diff['removed'])}. "
                  "See schema_drift.json for the exact list."]
    comparison = assessment["migration_comparison"]
    if comparison:
        lines += ["", "## Declared legacy system", "",
                  str(comparison["legacy_architecture"] or "Architecture evidence requested."),
                  "", f"Target: {comparison['target_architecture']}.", "",
                  "| Legacy field | Target field and type |", "|---|---|"]
        lines.extend(
            f"| {field} | {target or 'Mapping required'} |"
            for field, target in comparison["field_mapping"].items()
        )
    views = {
        "BI_BA": "Confirm the weighted denominator, filters and report output. Record metric sign-off.",
        "ARCHITECT": "Confirm the model grain, snapshot lineage, Delta destination and survey design fields.",
        "DEVELOPER": "Restrict eligible response codes to 1, 2, 3 and 4 with positive weights. Preserve the source weight.",
        "TESTER": "Rerun same-snapshot reconciliation. Check codes 7/9, nulls, zero weights and zero eligible groups.",
    }
    lines += ["", "## Reviewer views", ""]
    for role, task in views.items():
        lines += [f"### {role}", "", task, ""]
        for ticket in tickets:
            if ticket["role"] == role:
                lines.append(f"- {ticket['id']} ({ticket['status']}): {ticket['title']}")
        for finding in assessment["findings"]:
            if finding["role"] == role:
                lines.append(f"- {finding['message']}")
        lines.append("")
    lines += ["## Codebook evidence", ""]
    lines.extend(f"- [{doc['id']}]({doc['source']})" for doc in snippets)
    if not snippets:
        lines.append("Supply the CDC codebook archives to attach survey question evidence.")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
