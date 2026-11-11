# Deploy the claims demo on Databricks

Install the project package on Spark compute, using the runtime's PySpark. Upload the three synthetic CSV files and the `policies/` subfolder to an input volume. Import the notebooks in [notebooks/](../../notebooks/). Set the notebook widgets to your input and output volume paths. Use [sql/](../../sql/) to build views over the resulting Gold JSON.

This demo writes local or volume outputs in Parquet and JSON. The BRFSS workflow has a separate [Delta publishing guide](../../cloud/databricks/README.md).
