import tempfile
import unittest
from pathlib import Path

from healthcare.notifications.dispatcher import Outbox, dispatch


class ClaimNoticeTests(unittest.TestCase):
    def test_draft_requires_approval_and_deduplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            outbox = Outbox(Path(directory) / "outbox.sqlite")
            review = {"status": "REVIEW", "claim_id": "C002", "policy_version": "DEMO-2026",
                      "review_reasons": ["HIGH_AMOUNT", "COVERAGE"]}
            notice = outbox.draft(review)
            review["review_reasons"].reverse()
            self.assertEqual(notice, outbox.draft(review))
            self.assertEqual(len(outbox.list()), 1)
            self.assertEqual(dispatch(outbox), [])
            outbox.approve(notice, "Synthetic reviewer", "Checked fictional policy")
            self.assertEqual(dispatch(outbox)[0]["id"], notice)
            self.assertTrue(outbox.transition(notice, "APPROVED", "IN_FLIGHT"))
            self.assertFalse(outbox.transition(notice, "APPROVED", "IN_FLIGHT"))
            self.assertEqual(dispatch(outbox), [])

    def test_only_review_status_creates_draft(self):
        with tempfile.TemporaryDirectory() as directory:
            outbox = Outbox(Path(directory) / "outbox.sqlite")
            with self.assertRaisesRegex(ValueError, "Only flagged claims"):
                outbox.draft({"status": "QUARANTINED"})
