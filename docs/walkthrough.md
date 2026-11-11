# Follow the SatyaSetu migration

[Back to the README](../README.md)

SatyaSetu uses a synthetic fixture to demonstrate one specific migration error. The fixture models a dashboard that estimates diabetes prevalence by geography and survey year.

## 1. Stage the input

[Read the 2023 fixture](../data/sample/survey_2023.csv) alongside [the staging code](../src/brfss_assurance/input_data.py#L78). The pipeline assigns a year and row position, keeps the five survey fields used by the demo, and records the source file hash in the manifest.

## 2. Calculate the same metric twice

The [legacy Python calculation](../src/brfss_assurance/legacy.py#L8) and the [PySpark calculation](../src/brfss_assurance/spark_model.py#L35) use the same staged records. The baseline counts response codes 1–4 when the survey weight is positive. The target runs once with that same rule and once with a deliberate defect that also accepts codes 7 and 9.

For geography code 1 in the 2023 fixture, the weight for code 1 is **10**. The eligible denominator is **40**. The defect adds **160** to the denominator, leaving the numerator unchanged.

| Calculation | Numerator | Denominator | Weighted prevalence |
|---|---:|---:|---:|
| Legacy baseline | 10 | 40 | 25% |
| Corrected PySpark | 10 | 40 | 25% |
| PySpark with the deliberate defect | 10 | 200 | 5% |

## 3. Reconcile and review

[Reconciliation](../src/brfss_assurance/validation.py#L12) compares counts and weighted sums by survey year and geography. The demo flags the defective calculation, confirms that the corrected calculation matches, and writes the [Markdown report](../src/brfss_assurance/report.py#L24). After running the fixture, open `out/fixture/migration_report.md` to see the results.

The [requirement assessment](../src/brfss_assurance/requirements.py#L6) runs separately from reconciliation. It checks the proposed model and available source fields. The [ticket queue](../src/brfss_assurance/tickets.py#L12) records reviewer decisions. BI/BA sign-off follows the other applicable reviews.

## 4. Connect Azure if you need it

- [Databricks](../cloud/databricks/README.md) publishes validated tables to Delta.
- [Agent Bricks](../cloud/agent_bricks/README.md) can explain findings using retrieved CDC codebook evidence.
- [Logic Apps](../cloud/logic_apps/README.md) routes notifications to the assigned reviewers.
