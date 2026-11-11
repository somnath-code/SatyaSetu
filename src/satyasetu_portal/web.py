"""Private, single-instance review portal for the SatyaSetu demos."""

import argparse
import hmac
import ipaddress
import json
import os
import secrets
from pathlib import Path

from flask import (Flask, Response, abort, flash, redirect, render_template, request,
                   send_file, session, url_for)

from brfss_assurance.notify import dispatch as survey_dispatch
from brfss_assurance.requirements import assess
from brfss_assurance.tickets import Tickets
from healthcare.cli import explain, lookup
from healthcare.notifications.dispatcher import Outbox, dispatch as claims_dispatch

from .jobs import Jobs, TITLES, claim_rows, read_json

FILES = {
    "survey_fixture": ("migration_report.md", "assessment.json", "data_profile.json",
                       "reconciliation_corrected.json", "reconciliation_defect.json",
                       "manifest.json", "schema_drift.json", "retrieved_evidence.json"),
    "survey_full": ("migration_report.md", "assessment.json", "data_profile.json",
                    "reconciliation_corrected.json", "reconciliation_defect.json",
                    "manifest.json", "schema_drift.json", "retrieved_evidence.json"),
    "claims": ("summary.json", "policy_index.json"),
    "assessment": ("intake_assessment.json",),
}
SURVEYS = {"survey_fixture", "survey_full"}


def create_app(jobs, password=None, trusted_hosts=None):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=secrets.token_hex(32), MAX_CONTENT_LENGTH=48 * 1024,
        SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Strict",
        TRUSTED_HOSTS=trusted_hosts or ["localhost", "127.0.0.1", "[::1]"],
    )

    @app.before_request
    def protect():
        if request.endpoint == "health":
            return None
        if password:
            auth = request.authorization
            if (not auth or auth.type != "basic" or auth.username != "operator"
                    or not hmac.compare_digest((auth.password or "").encode(), password.encode())):
                return Response("Operator sign-in required.\n", 401,
                                {"WWW-Authenticate": 'Basic realm="SatyaSetu"'})
        if request.method == "POST":
            supplied = request.form.get("csrf", "")
            expected = session.get("csrf")
            if not expected or not hmac.compare_digest(supplied.encode(), expected.encode()):
                abort(400, "Reload the form and try again.")

    @app.after_request
    def headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; style-src 'self'; img-src 'self'; "
            "form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
        )
        if request.endpoint != "static":
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.context_processor
    def shared():
        if "csrf" not in session:
            session["csrf"] = secrets.token_urlsafe(32)
        return {"csrf": session["csrf"], "titles": TITLES}

    @app.get("/healthz")
    def health():
        return {"status": "ok"}

    @app.get("/")
    def home():
        sample = (jobs.repo / "examples/migration.json").read_text(encoding="utf-8")
        rows = jobs.recent()
        manifests = [r for r in rows if r["kind"] in SURVEYS and r["status"] == "SUCCEEDED"]
        return render_template("home.html", jobs=rows, full=jobs.has_full_data(),
                               sample=sample, manifests=manifests)

    @app.post("/runs")
    def launch():
        kind = request.form.get("kind", "")
        try:
            if kind == "assessment":
                content = request.form.get("requirement", "")
                if len(content.encode()) > 24 * 1024:
                    raise ValueError("Requirement JSON must be under 24 KB")
                doc = json.loads(content)
                catalog = read_json(jobs.repo / "config/catalog.json")
                assess(doc, catalog)
                manifest_id = request.form.get("manifest_id", type=int)
                if manifest_id is not None:
                    source = jobs.get(manifest_id)
                    if not source or source["kind"] not in SURVEYS or source["status"] != "SUCCEEDED":
                        raise ValueError("Choose a completed BRFSS run")
                job_id = jobs.enqueue(kind, json.dumps(doc), manifest_id)
            else:
                job_id = jobs.enqueue(kind)
        except (ValueError, TypeError) as exc:
            flash(str(exc), "error")
            return redirect(url_for("home"))
        return redirect(url_for("run", job_id=job_id), 303)

    def find_run(job_id, kinds=None, finished=False):
        job = jobs.get(job_id)
        if not job or (kinds and job["kind"] not in kinds):
            abort(404)
        if finished and job["status"] != "SUCCEEDED":
            abort(409, "Wait for this run to finish successfully.")
        return job, jobs.path(job_id)

    @app.get("/runs/<int:job_id>")
    def run(job_id):
        job, folder = find_run(job_id)
        result = None
        records, tickets, outputs, preview = [], [], [], []
        if job["status"] == "SUCCEEDED":
            outputs = [f for f in FILES[job["kind"]] if (folder / f).is_file()]
            if job["kind"] == "claims":
                result = read_json(folder / "summary.json")
                records = list(claim_rows(folder))
                queue = Outbox(folder / "claims_outbox.sqlite")
                tickets = queue.list()
                preview = claims_dispatch(queue)
            elif job["kind"] == "assessment":
                result = read_json(folder / "intake_assessment.json")
                tickets = Tickets(folder / "tickets.sqlite").list()
            else:
                assessment = read_json(folder / "assessment.json")
                corrected = read_json(folder / "reconciliation_corrected.json")
                defect = read_json(folder / "reconciliation_defect.json")
                result = {
                    "Design": assessment["verdict"],
                    "Corrected metric": corrected["status"],
                    "Matching groups": corrected["groups"] - corrected["failed_groups"],
                    "Defect mismatches": defect["failed_groups"],
                    "Source records": sum(r["rows"] for r in read_json(folder / "manifest.json")),
                    "Profile parity": read_json(folder / "data_profile.json")["status"],
                }
                tickets = Tickets(folder / "tickets.sqlite").list()
        return render_template("run.html", job=job, result=result, records=records,
                               tickets=tickets, outputs=outputs, preview=preview,
                               claims_configured=bool(os.getenv("CLAIMS_LOGIC_APP_CALLBACK_URL")),
                               survey_configured=bool(os.getenv("LOGIC_APP_CALLBACK_URL")))

    @app.get("/runs/<int:job_id>/files/<filename>")
    def artifact(job_id, filename):
        job, folder = find_run(job_id)
        if filename != "run.log" and (job["status"] != "SUCCEEDED"
                                      or filename not in FILES[job["kind"]]):
            abort(404)
        path = folder / filename
        if not path.is_file():
            abort(404)
        return send_file(path, mimetype="text/plain", as_attachment=True, download_name=filename)

    @app.get("/runs/<int:job_id>/claims/<claim_id>")
    def claim(job_id, claim_id):
        job, folder = find_run(job_id, {"claims"}, finished=True)
        try:
            data = explain(folder, claim_id)
        except ValueError:
            abort(404)
        return render_template("claim.html", job=job, item=data["claim"], evidence=data["evidence"])

    @app.post("/runs/<int:job_id>/claims/<claim_id>/draft")
    def draft(job_id, claim_id):
        _, folder = find_run(job_id, {"claims"}, finished=True)
        try:
            notice_id = Outbox(folder / "claims_outbox.sqlite").draft(lookup(folder, claim_id))
            flash(f"Draft {notice_id} is ready for approval.", "success")
        except ValueError as exc:
            flash(str(exc), "error")
        return redirect(url_for("run", job_id=job_id), 303)

    @app.post("/runs/<int:job_id>/review")
    def review(job_id):
        job, folder = find_run(job_id, finished=True)
        ref = request.form.get("reference", "")
        reviewer = request.form.get("reviewer", "").strip()
        note = request.form.get("note", "").strip()
        try:
            if len(reviewer) > 120 or len(note) > 1500:
                raise ValueError("Limit the reviewer name to 120 characters and the note to 1,500.")
            if job["kind"] == "claims":
                Outbox(folder / "claims_outbox.sqlite").approve(ref, reviewer, note)
            else:
                tickets = Tickets(folder / "tickets.sqlite")
                row = next((r for r in tickets.list() if r["id"] == ref), None)
                if not row:
                    raise ValueError("Ticket is missing.")
                tickets.decide(ref, row["role"], reviewer, request.form.get("decision", ""), note)
            flash(f"Review recorded for {ref}.", "success")
        except ValueError as exc:
            flash(str(exc), "error")
        return redirect(url_for("run", job_id=job_id), 303)

    @app.post("/runs/<int:job_id>/notify")
    def notify(job_id):
        job, folder = find_run(job_id, finished=True)
        try:
            if job["kind"] == "claims":
                results = claims_dispatch(Outbox(folder / "claims_outbox.sqlite"), send=True)
            else:
                results = survey_dispatch(Tickets(folder / "tickets.sqlite"), send=True)
            sent = sum(item["mode"] == "SENT" for item in results)
            flash(f"Sent {sent} of {len(results)} notices. Review any CHECK_DELIVERY statuses.",
                  "success" if sent == len(results) else "error")
        except ValueError as exc:
            flash(str(exc), "error")
        return redirect(url_for("run", job_id=job_id), 303)

    return app


def main():
    from waitress import serve

    parser = argparse.ArgumentParser(prog="satyasetu")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--state", type=Path, default=None)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    password = os.getenv("SATYASETU_PASSWORD")
    if not ipaddress.ip_address(args.host).is_loopback and not password:
        parser.error("Set SATYASETU_PASSWORD when binding outside loopback.")
    if password and len(password) < 16:
        parser.error("Use a SATYASETU_PASSWORD of at least 16 characters.")
    if not (args.repo / "data/sample/claims/claims.csv").is_file():
        parser.error("Run from the extracted SatyaSetu repository or set --repo.")
    jobs = Jobs(args.repo, args.state or args.repo / "out/portal")
    app = create_app(jobs, password)
    jobs.start()
    try:
        serve(app, host=args.host, port=args.port, threads=6, expose_tracebacks=False)
    finally:
        jobs.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
