"""Persistent single-worker queue for the two Spark workflows."""

import fcntl
import json
import os
import signal
import sqlite3
import subprocess
import sys
import threading
from contextlib import closing
from pathlib import Path

DATASETS = (
    ("--source-2023", "LLCP2023XPT.zip"),
    ("--source-2024", "LLCP2024XPT.zip"),
    ("--codebook-2023", "codebook23_llcp-v2-508.zip"),
    ("--codebook-2024", "codebook24_llcp-v2-508.zip"),
)
TITLES = {
    "survey_fixture": "Survey migration fixture",
    "survey_full": "Full BRFSS migration",
    "claims": "Synthetic claims review",
    "assessment": "Requirement assessment",
}


class Jobs:
    def __init__(self, repo, state):
        self.repo = Path(repo).resolve()
        self.state = Path(state).resolve()
        self.state.mkdir(parents=True, exist_ok=True)
        self.signal = threading.Event()
        self.stopping = threading.Event()
        with closing(self.connect()) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS job (
                id INTEGER PRIMARY KEY, kind TEXT NOT NULL, status TEXT NOT NULL,
                created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, finished TEXT, detail TEXT,
                request_json TEXT, manifest_job INTEGER
            )""")

    def connect(self):
        db = sqlite3.connect(self.state / "portal.sqlite", timeout=15)
        db.row_factory = sqlite3.Row
        return db

    def path(self, job_id):
        return self.state / "runs" / str(int(job_id))

    def has_full_data(self):
        return all((self.repo / "data/raw" / filename).is_file() for _, filename in DATASETS)

    def enqueue(self, kind, request_json=None, manifest_job=None):
        if kind not in TITLES or (kind == "assessment") != (request_json is not None):
            raise ValueError("Choose a supported workflow")
        if kind == "survey_full" and not self.has_full_data():
            raise ValueError("The four BRFSS archives must be present in data/raw")
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT COUNT(*) FROM job WHERE status IN ('QUEUED','RUNNING')").fetchone()[0] >= 10:
                raise ValueError("The queue already has ten active runs")
            job_id = db.execute(
                "INSERT INTO job(kind,status,request_json,manifest_job) VALUES (?,'QUEUED',?,?)",
                (kind, request_json, manifest_job),
            ).lastrowid
        self.signal.set()
        return job_id

    def recent(self, limit=25):
        with closing(self.connect()) as db:
            return [dict(row) for row in db.execute(
                "SELECT id,kind,status,created,finished,detail FROM job ORDER BY id DESC LIMIT ?",
                (limit,),
            )]

    def get(self, job_id):
        with closing(self.connect()) as db:
            row = db.execute("SELECT * FROM job WHERE id=?", (job_id,)).fetchone()
            return dict(row) if row else None

    def _take(self):
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM job WHERE status='QUEUED' ORDER BY id LIMIT 1").fetchone()
            if row:
                db.execute("UPDATE job SET status='RUNNING' WHERE id=?", (row["id"],))
            return row

    def _finish(self, job_id, status, detail=None):
        with closing(self.connect()) as db, db:
            db.execute("UPDATE job SET status=?,detail=?,finished=CURRENT_TIMESTAMP WHERE id=?",
                       (status, detail, job_id))

    def _command(self, job, folder):
        kind = job["kind"]
        output = ["--out", str(folder)]
        if kind == "claims":
            return [sys.executable, "-m", "healthcare.cli", "demo", *output]
        args = [sys.executable, "-m", "brfss_assurance.cli"]
        if kind == "assessment":
            request_path = folder / "request.json"
            request_path.write_text(job["request_json"], encoding="utf-8")
            command = args + ["assess", "--request", str(request_path), *output]
            if job["manifest_job"]:
                manifest = self.path(job["manifest_job"]) / "manifest.json"
                command.extend(["--manifest", str(manifest)])
            return command
        command = args + ["demo", *output]
        if kind == "survey_fixture":
            return command + ["--fixture"]
        for flag, filename in DATASETS:
            command.extend([flag, str(self.repo / "data/raw" / filename)])
        return command

    def _execute(self, job):
        folder = self.path(job["id"])
        folder.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ)
        env.setdefault("SPARK_LOCAL_IP", "127.0.0.1")
        env.pop("SATYASETU_PASSWORD", None)
        env.pop("LOGIC_APP_CALLBACK_URL", None)
        env.pop("CLAIMS_LOGIC_APP_CALLBACK_URL", None)
        with (folder / "run.log").open("wb") as log:
            with subprocess.Popen(self._command(job, folder), cwd=self.repo, env=env,
                                  stdout=log, stderr=subprocess.STDOUT,
                                  start_new_session=True) as proc:
                try:
                    for _ in range(900):
                        if self.stopping.is_set():
                            raise InterruptedError("Application stopped during the run")
                        try:
                            code = proc.wait(timeout=2)
                        except subprocess.TimeoutExpired:
                            continue
                        if code == 0:
                            self._finish(job["id"], "SUCCEEDED")
                        else:
                            self._finish(job["id"], "FAILED", f"Workflow exited with status {code}")
                        return
                    raise TimeoutError("Workflow exceeded its 30-minute time limit")
                finally:
                    if proc.poll() is None:
                        os.killpg(proc.pid, signal.SIGTERM)
                        try:
                            proc.wait(timeout=8)
                        except subprocess.TimeoutExpired:
                            os.killpg(proc.pid, signal.SIGKILL)
                            proc.wait()

    def start(self):
        self.lock = (self.state / ".worker.lock").open("a")
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            self.lock.close()
            raise RuntimeError("Another SatyaSetu instance is using this state directory") from exc
        with closing(self.connect()) as db, db:
            db.execute("""UPDATE job SET status='FAILED', finished=CURRENT_TIMESTAMP,
                       detail='Run interrupted by a server restart' WHERE status='RUNNING'""")
        self.thread = threading.Thread(target=self._work, daemon=True)
        self.thread.start()

    def stop(self):
        self.stopping.set()
        self.signal.set()
        self.thread.join(12)
        self.lock.close()

    def _work(self):
        while not self.stopping.is_set():
            job = self._take()
            if not job:
                self.signal.wait(1)
                self.signal.clear()
                continue
            try:
                self._execute(job)
            except (OSError, ValueError) as exc:
                self._finish(job["id"], "FAILED", str(exc))


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def claim_rows(folder, limit=100):
    from itertools import islice
    for path in sorted((folder / "gold/reviews").glob("part-*.json")):
        with path.open(encoding="utf-8") as stream:
            for line in islice(stream, limit):
                yield json.loads(line)
                limit -= 1
        if limit == 0:
            return
