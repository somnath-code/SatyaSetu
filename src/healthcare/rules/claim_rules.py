"""Apply the rules of the fictional DEMO-2026 policy to validated inputs."""

from pyspark.sql import Window, functions as F

POLICY_VERSION = "DEMO-2026"
RULE_IDS = frozenset({"COVERAGE", "LATE_FILING", "HIGH_AMOUNT", "REPEAT_ENCOUNTER"})


def apply_rules(valid):
    count = F.count("*").over(Window.partitionBy("encounter_id"))
    covered = ((F.col("plan_id") == "PLUS") & F.col("service_code").isin("VISIT", "LAB", "IMAGE")
               | (F.col("plan_id") == "BASIC") & F.col("service_code").isin("VISIT", "LAB"))
    threshold = F.when(F.col("plan_id") == "BASIC", 50_000).otherwise(100_000)
    reasons = F.array(
        F.when(~covered, F.lit("COVERAGE")),
        F.when(F.datediff("submitted_on", "service_date") > 30, F.lit("LATE_FILING")),
        F.when(F.col("billed_cents") > threshold, F.lit("HIGH_AMOUNT")),
        F.when(count > 1, F.lit("REPEAT_ENCOUNTER")),
    )
    return valid.withColumn("review_reasons", F.filter(reasons, lambda x: x.isNotNull()))
