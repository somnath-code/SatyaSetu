# Data model

## Claims

| Dataset | Grain and key | Contents |
|---|---|---|
| Patients | One row per `patient_id` | Synthetic ID and plan ID |
| Encounters | One row per `encounter_id` | Patient ID, service code, and service date |
| Claims | One row per `claim_id` | Encounter ID, billed cents, and submission date |
| Silver claim context | One row per `claim_id` | Validated join, typed amounts and dates, quality issue codes |
| Gold review | One row per `claim_id` | Status, review reasons, quality issues, and policy version |

Silver uses left joins so claims with missing references remain visible as quality issues. Gold retains a synthetic claim ID for lookup. A notification includes the claim ID, policy version, rule IDs, and notice ID.

## Survey migration

The BRFSS target fact uses one row per survey response with a snapshot-relative key of survey year and source row position. Its Gold estimate groups by survey year and geography. See the [BRFSS data model and metric](brfss-migration.md#data-model-and-metric).
