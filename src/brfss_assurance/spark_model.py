"""Build the target fact, profile response quality, and aggregate the BI metric."""

from pyspark.sql import SparkSession, functions as F

STAGING_SCHEMA = (
    "survey_year INT, source_row LONG, _STATE INT, DIABETE4 INT, "
    "_LLCPWT DECIMAL(24,8), _STSTR LONG, _PSU LONG"
)
VALID_CODES = [1, 2, 3, 4]
UNKNOWN_CODES = [7, 9]


def build_spark(local):
    builder = SparkSession.builder.appName("BRFSS migration assurance")
    if local:
        builder = (builder.master("local[2]").config("spark.ui.enabled", "false")
                   .config("spark.sql.shuffle.partitions", "4"))
    return builder.getOrCreate()


def read_bronze(spark, stage_paths):
    return spark.read.schema(STAGING_SCHEMA).option("header", True).option(
        "mode", "FAILFAST"
    ).csv([str(path) for path in stage_paths])


def survey_fact(bronze):
    return bronze.selectExpr(
        "survey_year", "source_row", "_STATE AS state_code",
        "DIABETE4 AS diabetes_response_code", "_LLCPWT AS final_weight",
        "_STSTR AS stratum", "_PSU AS primary_sampling_unit",
    )


def aggregate(fact, *, inject_defect=False):
    code = F.col("diabetes_response_code")
    weight = F.col("final_weight")
    positive = weight.isNotNull() & (weight > 0)
    allowed_codes = VALID_CODES + UNKNOWN_CODES if inject_defect else VALID_CODES
    eligible = positive & code.isin(allowed_codes)
    case = positive & (code == 1)
    return fact.groupBy("survey_year", "state_code").agg(
        F.count("*").alias("rows"),
        F.count_if(eligible).alias("eligible"),
        F.count_if(case).alias("cases"),
        F.coalesce(F.sum(weight), F.lit(0)).alias("all_weight"),
        F.sum(F.when(case, weight).otherwise(F.lit(0))).alias("numerator"),
        F.sum(F.when(eligible, weight).otherwise(F.lit(0))).alias("denominator"),
    )


def profile(fact):
    code = F.col("diabetes_response_code")
    weight = F.col("final_weight")
    groups = fact.groupBy("survey_year").agg(
        F.count("*").alias("rows"),
        (F.count("*") - F.countDistinct("source_row")).alias("duplicate_source_keys"),
        F.countDistinct("state_code").alias("distinct_geographies"),
        F.count_if(F.col("state_code").isNull()).alias("missing_geography"),
        F.count_if(code.isNull()).alias("null_response"),
        F.count_if(code == 7).alias("dont_know"),
        F.count_if(code == 9).alias("refused"),
        F.count_if(~code.isin(VALID_CODES + UNKNOWN_CODES)).alias("invalid_response"),
        F.count_if(weight.isNull() | (weight <= 0)).alias("invalid_weight"),
        F.count_if(F.col("stratum").isNull()).alias("missing_stratum"),
        F.count_if(F.col("primary_sampling_unit").isNull()).alias("missing_psu"),
        F.min(weight).alias("min_weight"),
        F.max(weight).alias("max_weight"),
    )
    codes = fact.groupBy("survey_year", "diabetes_response_code").count()
    return {
        "summary": [r.asDict() for r in groups.orderBy("survey_year").collect()],
        "response_distribution": [r.asDict() for r in codes.orderBy(
            "survey_year", "diabetes_response_code").collect()],
    }


def publish_delta(bronze, fact, gold, prefix):
    import re

    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*[.][A-Za-z_][A-Za-z0-9_]*", prefix):
        raise ValueError("Delta destination must be catalog.schema with simple identifiers")
    for name, frame in (
        ("bronze_survey_projection", bronze), ("fact_survey_response", fact),
        ("dim_geography", fact.select("state_code").where("state_code IS NOT NULL").distinct()),
        ("dim_survey_year", fact.select("survey_year").distinct()),
        ("gold_diabetes_by_geography", gold.withColumn(
            "prevalence_pct", F.when(F.col("denominator") > 0,
                                     100.0 * F.col("numerator") / F.col("denominator")))),
    ):
        frame.write.format("delta").mode("overwrite").saveAsTable(f"{prefix}.{name}")
