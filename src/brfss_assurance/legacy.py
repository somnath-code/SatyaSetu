"""Independent reference implementation of the simulated legacy metric."""

import csv
from collections import defaultdict
from decimal import Decimal


def calculate(stage_path):
    totals = defaultdict(lambda: {
        "rows": 0, "eligible": 0, "cases": 0,
        "all_weight": Decimal("0"), "numerator": Decimal("0"),
        "denominator": Decimal("0"),
    })
    with stage_path.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            key = (int(row["survey_year"]), int(row["_STATE"]) if row["_STATE"] else None)
            total = totals[key]
            total["rows"] += 1
            weight = Decimal(row["_LLCPWT"]) if row["_LLCPWT"] else Decimal("0")
            total["all_weight"] += weight
            if row["DIABETE4"] not in {"1", "2", "3", "4"} or weight <= 0:
                continue
            total["eligible"] += 1
            total["denominator"] += weight
            if row["DIABETE4"] == "1":
                total["cases"] += 1
                total["numerator"] += weight
    return [{"survey_year": year, "state_code": state, **metrics}
            for (year, state), metrics in totals.items()]
