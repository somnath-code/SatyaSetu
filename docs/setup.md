# Set up SatyaSetu

Use Python 3.11 or 3.12 and Java 17 or 21. Install and run the two fixtures from the [README](../README.md#run-both-demos). If Spark cannot resolve your hostname in WSL, set `SPARK_LOCAL_IP=127.0.0.1`.

To generate more synthetic claim records:

~~~bash
python scripts/generate_synthetic_data.py --count 500 --out out/generated-claims
claims demo --data out/generated-claims --out out/generated-run
~~~

For full survey data, follow the [CDC input guide](brfss-migration.md#run-the-cdc-files). For cloud setup, use the [claims Databricks guide](../deployment/databricks/README.md), [claims Agent Bricks tool guide](../agent/README.md), and [claims Logic Apps template guide](../deployment/logic-apps/README.md). The existing survey guides are in [cloud/](../cloud/).
