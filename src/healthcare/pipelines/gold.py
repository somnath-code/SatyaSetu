"""Produce claim review statuses and a compact BI summary."""

from pyspark.sql import functions as F

from healthcare.rules.claim_rules import POLICY_VERSION, apply_rules


def review(silver):
    valid = silver.filter(F.size("quality_issues") == 0)
    flagged = apply_rules(valid).withColumn(
        "status", F.when(F.size("review_reasons") > 0, "REVIEW").otherwise("PASS")
    )
    quarantine = (silver.filter(F.size("quality_issues") > 0)
                  .withColumn("review_reasons", F.array().cast("array<string>"))
                  .withColumn("status", F.lit("QUARANTINED")))
    return (flagged.unionByName(quarantine).withColumn("policy_version", F.lit(POLICY_VERSION))
            .select("claim_id", "plan_id", "service_code", "billed_cents", "status",
                    "review_reasons", "quality_issues", "policy_version"))


def summarize(reviews):
    return reviews.groupBy("status").agg(F.count("*").alias("claims"))
