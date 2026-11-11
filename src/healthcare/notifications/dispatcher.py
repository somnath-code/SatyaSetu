"""Keep claim notification drafts and send only approved metadata."""

import hashlib
import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, build_opener

from brfss_assurance.notify import NoRedirect


class Outbox:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS claims_outbox (
                id TEXT PRIMARY KEY, payload TEXT NOT NULL,
                state TEXT NOT NULL DEFAULT 'PENDING_APPROVAL',
                reviewer TEXT, note TEXT, approved_at TEXT
            )""")

    def connect(self):
        db = sqlite3.connect(self.path, timeout=20)
        db.row_factory = sqlite3.Row
        return db

    def draft(self, review):
        if review["status"] != "REVIEW" or not review["review_reasons"]:
            raise ValueError("Only flagged claims can be drafted for notification")
        payload = {
            "kind": "claim_review",
            "claim_id": review["claim_id"],
            "policy_version": review["policy_version"],
            "rules": sorted(review["review_reasons"]),
        }
        key = json.dumps(payload, sort_keys=True).encode()
        payload["id"] = "CL-" + hashlib.sha256(key).hexdigest()[:16]
        with closing(self.connect()) as db, db:
            db.execute("INSERT OR IGNORE INTO claims_outbox (id, payload) VALUES (?, ?)",
                       (payload["id"], json.dumps(payload, sort_keys=True)))
        return payload["id"]

    def approve(self, notice_id, reviewer, note):
        if not reviewer.strip() or not note.strip():
            raise ValueError("Provide reviewer and approval note")
        with closing(self.connect()) as db, db:
            changed = db.execute("""UPDATE claims_outbox
                SET state = 'APPROVED', reviewer = ?, note = ?, approved_at = CURRENT_TIMESTAMP
                WHERE id = ? AND state = 'PENDING_APPROVAL'""", (reviewer, note, notice_id))
            if changed.rowcount != 1:
                raise ValueError("Notification is missing or has already been reviewed")

    def list(self):
        with closing(self.connect()) as db:
            return [{"payload": json.loads(row["payload"]), "state": row["state"],
                     "reviewer": row["reviewer"], "note": row["note"],
                     "approved_at": row["approved_at"]}
                    for row in db.execute("SELECT * FROM claims_outbox ORDER BY id")]

    def transition(self, notice_id, old, new):
        with closing(self.connect()) as db, db:
            result = db.execute("UPDATE claims_outbox SET state = ? WHERE id = ? AND state = ?",
                                (new, notice_id, old))
            return result.rowcount == 1


def dispatch(outbox, send=False):
    candidates = [row["payload"] for row in outbox.list() if row["state"] == "APPROVED"]
    if not send:
        return [{"mode": "DRY_RUN", **payload} for payload in candidates]

    url = os.environ.get("CLAIMS_LOGIC_APP_CALLBACK_URL", "")
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        raise ValueError("Set CLAIMS_LOGIC_APP_CALLBACK_URL to an HTTPS workflow URL")
    opener = build_opener(NoRedirect())
    results = []
    for payload in candidates:
        notice_id = payload["id"]
        if not outbox.transition(notice_id, "APPROVED", "IN_FLIGHT"):
            continue
        delivered = False
        try:
            request = Request(url, data=json.dumps(payload).encode("utf-8"),
                              headers={"Content-Type": "application/json"}, method="POST")
            with opener.open(request, timeout=30) as response:
                delivered = response.status == 200
        except OSError:
            # Azure might have accepted the request before the connection failed.
            pass
        status = "SENT" if delivered else "CHECK_DELIVERY"
        outbox.transition(notice_id, "IN_FLIGHT", status)
        results.append({"mode": status, **payload})
    return results
