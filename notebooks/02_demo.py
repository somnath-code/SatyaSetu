# Databricks notebook source
from healthcare.cli import run_demo

# COMMAND ----------
dbutils.widgets.text("claims_input", "/Volumes/demo/health/input/claims")
dbutils.widgets.text("claims_output", "/Volumes/demo/health/output/claims")
result = run_demo(dbutils.widgets.get("claims_input"), dbutils.widgets.get("claims_output"))
print(result["counts"])
display(spark.read.json(result["reviews"]))
