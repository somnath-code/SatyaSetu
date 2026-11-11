"""Check the keys needed for deterministic claims joins."""

from pyspark.sql import functions as F

KEYS = {"patients": "patient_id", "encounters": "encounter_id", "claims": "claim_id"}


def check_source_keys(tables):
    for table, key in KEYS.items():
        grouped = tables[table].groupBy(key).count()
        bad = grouped.filter(F.col(key).isNull() | (F.col(key) == "") | (F.col("count") > 1))
        if bad.limit(1).count():
            raise ValueError(f"{table}.{key} must be present and unique")
