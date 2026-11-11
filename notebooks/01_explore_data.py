# Databricks notebook source
from healthcare.pipelines.bronze import load

# COMMAND ----------
dbutils.widgets.text("claims_input", "/Volumes/demo/health/input/claims")
frames = load(spark, dbutils.widgets.get("claims_input"))
for name, frame in frames.items():
    print(name, frame.count())
    display(frame)
