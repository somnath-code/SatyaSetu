"""Return a preview for human review. This tool never writes or sends a notification."""
from .lookup_claim import lookup_claim


def draft_notification(claim_id: str) -> dict:
    claim = lookup_claim(claim_id)
    if claim["status"] != "REVIEW":
        return {"claim_id": claim_id, "status": claim["status"], "draft_available": False}
    return {"claim_id": claim_id, "policy_version": claim["policy_version"],
            "rules": claim["review_reasons"], "draft_available": True,
            "next_step": "A human reviewer can draft and approve this notice in the claims CLI."}
