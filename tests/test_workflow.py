import json
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from zipfile import ZipFile

from brfss_assurance.cli import main
from brfss_assurance.evidence import retrieve
from brfss_assurance.input_data import archive_member
from brfss_assurance.notify import dispatch
from brfss_assurance.requirements import assess
from brfss_assurance.tickets import Tickets

ROOT = Path(__file__).resolve().parents[1]


class WorkflowTests(unittest.TestCase):
    def test_custom_ticket_database_is_used_by_review_commands(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "review.sqlite"
            store = Tickets(path)
            ticket = store.create({"id": "DEMO", "version": 1},
                                  "DEFECT", "DEVELOPER", "Check denominator")
            preview = io.StringIO()
            with redirect_stdout(preview):
                self.assertEqual(main(["notify", "--ticket-db", str(path)]), 0)
            self.assertEqual(json.loads(preview.getvalue())[0]["id"], ticket)
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main([
                    "decide", ticket, "--ticket-db", str(path),
                    "--role", "DEVELOPER", "--actor", "Reviewer",
                    "--decision", "APPROVED", "--note", "Confirmed evidence",
                ]), 0)
            self.assertEqual(store.list()[0]["status"], "APPROVED")

    def test_requirement_outcomes(self):
        catalog = json.loads((ROOT / "config/catalog.json").read_text())
        for filename, expected in (
            ("migration.json", "SUITABLE"),
            ("missing_legacy.json", "NEEDS_CLARIFICATION"),
            ("unsupported_grain.json", "UNSUITABLE_AS_PROPOSED"),
        ):
            with self.subTest(filename=filename):
                request = json.loads((ROOT / "examples" / filename).read_text())
                self.assertEqual(assess(request, catalog)["verdict"], expected)

    def test_deduplication_routing_and_signoff(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Tickets(Path(folder) / "queue.sqlite")
            req = {"id": "DEMO", "version": 1}
            dev = store.create(req, "DEFECT", "DEVELOPER", "Check denominator")
            self.assertEqual(dev, store.create(req, "DEFECT", "DEVELOPER", "Check denominator"))
            signoff = store.create(req, "METRIC_SIGNOFF", "BI_BA", "Approve")
            self.assertEqual(len(dispatch(store)), 2)
            with self.assertRaisesRegex(ValueError, "given role"):
                store.decide(dev, "BI_BA", "reviewer", "APPROVED", "wrong role")
            with self.assertRaisesRegex(ValueError, "other review tickets"):
                store.decide(signoff, "BI_BA", "reviewer", "APPROVED", "premature")
            store.decide(dev, "DEVELOPER", "developer", "APPROVED", "corrected")
            store.decide(signoff, "BI_BA", "reviewer", "APPROVED", "verified")
            self.assertFalse(dispatch(store))

    def test_zip_member_with_trailing_spaces(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "test.zip"
            with ZipFile(path, "w") as archive:
                archive.writestr("SURVEY.XPT  ", b"demo")
            with archive_member(path, ".xpt") as stream:
                self.assertEqual(stream.read(), b"demo")

    def test_retrieval_respects_year_and_exact_field(self):
        docs = [
            {"id": "2023:GENHLTH", "year": 2023, "field": "GENHLTH", "text": "general health"},
            {"id": "2023:DIABETE4", "year": 2023, "field": "DIABETE4", "text": "DIABETE4 diabetes"},
            {"id": "2024:DIABETE4", "year": 2024, "field": "DIABETE4", "text": "DIABETE4 diabetes"},
        ]
        hits = retrieve(docs, "DIABETE4 health", year=2023)
        self.assertEqual([doc["id"] for doc in hits], ["2023:DIABETE4", "2023:GENHLTH"])


if __name__ == "__main__":
    unittest.main()
