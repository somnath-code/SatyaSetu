"""Compare matching source slices and emit auditable check evidence."""

from decimal import Decimal

FIELDS = ("rows", "eligible", "cases", "all_weight", "numerator", "denominator")


def percentage(row):
    return Decimal(100) * row["numerator"] / row["denominator"] if row["denominator"] else None


def reconcile(reference, target):
    def index(rows):
        result = {}
        for row in rows:
            key = (row["survey_year"], row["state_code"])
            if key in result:
                raise ValueError(f"Duplicate aggregation group {key}")
            result[key] = row
        return result

    expected = index(reference)
    actual = index(target)
    comparisons = []
    for key in sorted(expected.keys() | actual.keys(), key=lambda k: (k[0], k[1] or -1)):
        left, right = expected.get(key), actual.get(key)
        failures = ["missing_group"] if left is None or right is None else [
            field for field in FIELDS if left[field] != right[field]
        ]
        comparisons.append({
            "survey_year": key[0], "state_code": key[1],
            "expected": left, "actual": right, "failed_checks": failures,
            "expected_prevalence_pct": percentage(left) if left else None,
            "actual_prevalence_pct": percentage(right) if right else None,
        })
    return {
        "status": "PASS" if comparisons and not any(
            row["failed_checks"] for row in comparisons) else "FAIL",
        "groups": len(comparisons),
        "failed_groups": sum(bool(row["failed_checks"]) for row in comparisons),
        "comparisons": comparisons,
    }


def source_schema_diff(before, after):
    earlier = set(before["source_columns"])
    later = set(after["source_columns"])
    return {
        "from_year": before["year"], "to_year": after["year"],
        "from_field_count": len(earlier), "to_field_count": len(later),
        "removed": sorted(earlier - later), "added": sorted(later - earlier),
        "metric_fields_missing": sorted(
            {"_STATE", "DIABETE4", "_LLCPWT"} - later),
    }
