# Synthetic claims business rules

The [fictional policy](../data/sample/claims/policies/fictional-claims-policy.md) describes the rules implemented in [claim_rules.py](../src/healthcare/rules/claim_rules.py). Amounts are stored as integer cents.

| Rule | Flag when |
|---|---|
| `COVERAGE` | BASIC requests a service outside VISIT and LAB, or PLUS requests a service outside VISIT, LAB, and IMAGE. |
| `LATE_FILING` | More than 30 calendar days elapsed between service and submission. |
| `HIGH_AMOUNT` | The billed amount exceeds 50,000 cents for BASIC or 100,000 cents for PLUS. |
| `REPEAT_ENCOUNTER` | Two or more valid claims reference the same encounter. Each goes to review. |

A claim with broken references, an invalid amount, invalid dates, or missing policy context is `QUARANTINED`. Otherwise, at least one flag yields `REVIEW`. A record with no flags yields `PASS` for the demo checks. These are review statuses for synthetic records.
