# Fictional claims review policy DEMO-2026

This synthetic policy exists for the SatyaSetu demo. Amounts are in cents. Review flags request human review and carry no payment decision.

## COVERAGE — Services covered by each plan

BASIC covers VISIT and LAB. PLUS covers VISIT, LAB and IMAGE. Review any service code outside the listed coverage for the plan.

## LATE_FILING — Filing deadline

Submit within 30 calendar days of the service date. A submission at exactly 30 days is within the filing window. Review claims submitted after that window.

## HIGH_AMOUNT — Amount threshold

Review amounts over 50,000 cents for BASIC or over 100,000 cents for PLUS. Amounts equal to the threshold remain within the limit.

## REPEAT_ENCOUNTER — Multiple claims for one encounter

When two or more valid claim records reference the same encounter, review all those records. An encounter can legitimately have several submissions, so a repeat is a review flag.

## QUALITY — Incomplete claim data

Quarantine rows with missing encounter or patient references, an invalid amount, invalid dates, or missing policy context. Resolve data quality issues before applying the review rules.
