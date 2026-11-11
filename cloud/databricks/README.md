# Publish the target model as Delta tables

Use the same project in an Azure Databricks workspace with an existing Unity Catalog schema and a writable volume. Put the CSV fixture or downloaded BRFSS archives and codebooks in the volume. Use a dedicated demo schema because the job overwrites its named tables.

1. Import the project into a Databricks Git folder. On cluster-backed compute, install the project package with `%pip install -e /Workspace/path/to/satyasetu`. Use the runtime's bundled PySpark and ensure pandas is available for reading XPT files.
2. Run the following from a Databricks Python notebook attached to the compute. Set the paths to match your workspace.

~~~python
from brfss_assurance.cli import main

result = main([
    "demo",
    "--request", "/Workspace/path/to/satyasetu/examples/migration.json",
    "--catalog", "/Workspace/path/to/satyasetu/config/catalog.json",
    "--source-2023", "/Volumes/demo/health/inputs/brfss/LLCP2023XPT.zip",
    "--source-2024", "/Volumes/demo/health/inputs/brfss/LLCP2024XPT.zip",
    "--codebook-2023", "/Volumes/demo/health/inputs/brfss/codebook23_llcp-v2-508.zip",
    "--codebook-2024", "/Volumes/demo/health/inputs/brfss/codebook24_llcp-v2-508.zip",
    "--out", "/Volumes/demo/health/inputs/brfss_output",
    "--ticket-db", "/local_disk0/brfss_demo/tickets.sqlite",
    "--delta-destination", "demo.health",
])
if result:
    raise RuntimeError("Review the migration report before publishing the Delta tables.")
~~~

The job publishes the Bronze survey projection, Silver survey fact, year and geography dimensions, and Gold diabetes summary after the design is marked suitable and both parity checks pass. It writes each table separately, so use a dedicated demo schema. Test the notebook interactively before scheduling it as a Databricks job.

The example stores SQLite on the compute's local disk. To view or record decisions from the same machine, pass the same `--ticket-db` path to `brfss tickets`, `brfss notify`, or `brfss decide`. For a shared, durable ticket workflow, use a transactional database or a tracker.
