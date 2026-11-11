"""Build the local policy lookup index used by the CLI and agent tools."""

import json
from pathlib import Path

from healthcare.rag.ingest_documents import load_policy
from healthcare.rules.claim_rules import RULE_IDS


def build(policy_file, output):
    index = load_policy(policy_file)
    missing = RULE_IDS - index.keys()
    if missing:
        raise ValueError(f"Missing policy explanations: {', '.join(sorted(missing))}")
    Path(output).write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n",
                            encoding="utf-8")
    return index
