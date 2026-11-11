"""Return synthetic claim review data for a configured demo run."""
import os
from healthcare.cli import lookup


def lookup_claim(claim_id: str) -> dict:
    return lookup(os.environ.get("SATYASETU_CLAIMS_OUT", "out/claims"), claim_id)
