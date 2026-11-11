"""Read-only tools to add to the Agent Bricks LangGraph scaffold."""

import json
import os
from pathlib import Path

from langchain_core.tools import tool

from brfss_assurance.evidence import retrieve


def load_evidence(filename):
    directory = Path(os.environ["BRFSS_EVIDENCE_DIR"])
    return json.loads((directory / filename).read_text(encoding="utf-8"))


@tool
def search_brfss_codebook(query: str, survey_year: int) -> list[dict]:
    """Find up to three cited codebook entries for one BRFSS survey year."""
    if survey_year not in (2023, 2024):
        return []
    matches = retrieve(load_evidence("codebook_index.json"), query, survey_year)
    return [{**document, "text": document["text"][:2400]} for document in matches]


@tool
def migration_validation_summary() -> dict:
    """Read recorded check results and a representative mismatch from the demo."""
    result = {}
    for scenario in ("corrected", "defect"):
        report = load_evidence(f"reconciliation_{scenario}.json")
        result[scenario] = {k: report[k] for k in ("status", "groups", "failed_groups")}
        result[scenario]["example_mismatch"] = next(
            (item for item in report["comparisons"] if item["failed_checks"]), None
        )
    assessment = load_evidence("assessment.json")
    result["requirement"] = {k: assessment[k] for k in
                             ("id", "version", "verdict", "validation_status")}
    return result
