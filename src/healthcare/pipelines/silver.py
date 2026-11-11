"""Join claim context and separate records with missing or unusable inputs."""

from pyspark.sql import functions as F


def prepare(tables):
    encounter = tables["encounters"].withColumn("_encounter_found", F.lit(True))
    patient = tables["patients"].withColumn("_patient_found", F.lit(True))
    joined = (tables["claims"].join(encounter, "encounter_id", "left")
              .join(patient, "patient_id", "left")
              .withColumn("billed_cents", F.expr("try_cast(billed_cents as bigint)"))
              .withColumn("service_date", F.expr("try_cast(service_date as date)"))
              .withColumn("submitted_on", F.expr("try_cast(submitted_on as date)")))

    issues = F.array(
        F.when(F.col("_encounter_found").isNull(), F.lit("MISSING_ENCOUNTER")),
        F.when(F.col("_encounter_found").isNotNull() & F.col("_patient_found").isNull(),
               F.lit("MISSING_PATIENT")),
        F.when(F.col("billed_cents").isNull() | (F.col("billed_cents") <= 0),
               F.lit("INVALID_AMOUNT")),
        F.when(F.col("service_date").isNull() | F.col("submitted_on").isNull()
               | (F.col("submitted_on") < F.col("service_date")), F.lit("INVALID_DATES")),
        F.when(F.col("service_code").isNull() | (F.col("service_code") == "")
               | ~F.col("plan_id").isin("BASIC", "PLUS") | F.col("plan_id").isNull(),
               F.lit("MISSING_POLICY_CONTEXT")),
    )
    return (joined.withColumn("quality_issues", F.filter(issues, lambda x: x.isNotNull()))
            .drop("_encounter_found", "_patient_found"))
