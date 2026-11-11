"""Read the synthetic source files without inferring types."""

from pyspark.sql import functions as F

COLUMNS = {
    "patients": ("patient_id", "plan_id"),
    "encounters": ("encounter_id", "patient_id", "service_code", "service_date"),
    "claims": ("claim_id", "encounter_id", "billed_cents", "submitted_on"),
}


def load(spark, data_dir):
    tables = {}
    for name, columns in COLUMNS.items():
        table = (spark.read.option("header", True).option("enforceSchema", False)
                 .option("mode", "FAILFAST")
                 .schema(", ".join(f"{col} STRING" for col in columns))
                 .csv(f"{data_dir}/{name}.csv"))
        tables[name] = table.select(*(F.trim(F.col(col)).alias(col) for col in columns))
    return tables
