"""Find the fictional policy sections that can support an explanation."""
import os
from healthcare.cli import policy_index
from healthcare.rag.retrieve import search


def search_policy(query: str) -> list[dict]:
    index = policy_index(os.environ.get("SATYASETU_CLAIMS_OUT", "out/claims"))
    return search(index, query)
