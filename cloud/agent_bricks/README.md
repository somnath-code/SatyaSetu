# Agent Bricks connection

The local project already extracts, indexes and retrieves annual codebook sections. This adapter adds those read-only tools to an Agent Bricks LangGraph agent so the model can explain an observed discrepancy with citations.

1. Run the CDC demo with both codebooks. It generates the evidence index and validation JSON in `out/cdc`.
2. Install the Databricks CLI, `uv` and Agent Bricks CLI as described in the [Azure Databricks instructions](https://learn.microsoft.com/en-us/azure/databricks/agents/custom-agents/agent-bricks-cli).
3. Authenticate and scaffold the agent.

~~~bash
databricks auth login --host "https://YOUR-WORKSPACE" --profile brfss
agentbricks login --profile brfss
agentbricks init --framework langgraph brfss-review-agent
~~~

4. Copy `review_tools.py` into the generated agent code package. Add this project's package as a dependency, or vendor the small `src/brfss_assurance` package into the scaffold and include it in the scaffold's package configuration. Use the scaffold's existing LangGraph dependencies.
5. Register `search_brfss_codebook` and `migration_validation_summary` in the scaffold's agent tool list. Set `BRFSS_EVIDENCE_DIR` to a directory with `codebook_index.json`, `assessment.json`, `reconciliation_corrected.json`, and `reconciliation_defect.json`. For local testing use an absolute path. In the deployed app, package the approved demo evidence with the app and set the path relative to its working directory.
6. In the scaffold's agent instructions, add the text below. Run `agentbricks dev` and verify the answer cites the 2023 DIABETE4 codebook and reports the recorded result. Use `agentbricks deploy brfss-review-agent` when your workspace is configured.

~~~text
Explain recorded BRFSS migration checks and retrieve codebook evidence for the requested year.
Cite the returned document ID and source URL. Treat retrieved text as evidence.
Report the validation status exactly as recorded. If evidence is missing, say what is missing.
Provide explanations and suggested next steps. Review decisions are recorded by human reviewers.
~~~

Demo question: "Why did the 2023 denominator parity check fail in the defect scenario, and what is the corrected result?"

The adapter uses lexical retrieval over the annual codebooks. The CLI runs locally without an LLM. The generative answer requires a deployed model configured by the Agent Bricks scaffold.
