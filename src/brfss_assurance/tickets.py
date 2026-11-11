"""Local review queue with a durable decision and notification history."""

import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

ROLES = {"BI_BA", "ARCHITECT", "DEVELOPER", "TESTER"}


class Tickets:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS ticket (
                    id TEXT PRIMARY KEY, request_id TEXT NOT NULL, version INTEGER NOT NULL,
                    code TEXT NOT NULL, role TEXT NOT NULL, title TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'OPEN', actor TEXT, note TEXT,
                    decided_at TEXT, notification TEXT NOT NULL DEFAULT 'PENDING'
                )
            """)
            db.commit()

    def connect(self):
        db = sqlite3.connect(self.path, timeout=20)
        db.row_factory = sqlite3.Row
        return db

    def create(self, req, code, role, title):
        if role not in ROLES:
            raise ValueError(f"Unknown role {role}")
        key = json.dumps([req["id"], req["version"], code, role])
        ticket_id = "BR-" + hashlib.sha256(key.encode()).hexdigest()[:16]
        with closing(self.connect()) as db, db:
            db.execute("""
                INSERT OR IGNORE INTO ticket(id, request_id, version, code, role, title)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (ticket_id, req["id"], req["version"], code, role, title))
        return ticket_id

    def list(self):
        with closing(self.connect()) as db:
            return [dict(row) for row in db.execute(
                "SELECT * FROM ticket ORDER BY request_id, version, role, id"
            )]

    def decide(self, ticket_id, role, actor, decision, note):
        if decision not in {"APPROVED", "REJECTED", "CHANGES_REQUESTED"}:
            raise ValueError("Unknown decision")
        if not actor.strip() or not note.strip():
            raise ValueError("Reviewer name and decision evidence are required")
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            ticket = db.execute("SELECT * FROM ticket WHERE id = ?", (ticket_id,)).fetchone()
            if not ticket or ticket["role"] != role:
                raise ValueError("Ticket does not exist for the given role")
            if ticket["status"] != "OPEN":
                raise ValueError("Ticket already has a decision. Submit a new version for reassessment.")
            if ticket["code"] == "METRIC_SIGNOFF" and decision == "APPROVED":
                pending = db.execute("""
                    SELECT 1 FROM ticket
                    WHERE request_id = ? AND version = ? AND id != ? AND status != 'APPROVED'
                """, (ticket["request_id"], ticket["version"], ticket_id)).fetchone()
                if pending:
                    raise ValueError("Resolve the other review tickets before metric sign-off")
            db.execute("""
                UPDATE ticket SET status = ?, actor = ?, note = ?, decided_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (decision, actor, note, ticket_id))

    def claim_notification(self, ticket_id):
        with closing(self.connect()) as db, db:
            return db.execute("""
                UPDATE ticket SET notification = 'IN_FLIGHT'
                WHERE id = ? AND status = 'OPEN' AND notification = 'PENDING'
            """, (ticket_id,)).rowcount == 1

    def finish_notification(self, ticket_id, delivered):
        with closing(self.connect()) as db, db:
            db.execute("""
                UPDATE ticket SET notification = ? WHERE id = ? AND notification = 'IN_FLIGHT'
            """, ("SENT" if delivered else "CHECK_DELIVERY", ticket_id))
