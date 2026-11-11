"""Run an end-to-end portal smoke test through HTTP with local Spark subprocesses."""

import argparse
import json
import os
import re
import signal
import socket
import subprocess
import sys
import time
from html import unescape
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, build_opener


def exercise(base, full):
    browser = build_opener(HTTPCookieProcessor())

    def get(path, form=None):
        data = None if form is None else urlencode(form).encode()
        with browser.open(base + path, data=data, timeout=15) as reply:
            return reply.geturl(), reply.read().decode()

    for _ in range(60):
        try:
            _, home = get("/")
            break
        except URLError:
            time.sleep(0.25)
    else:
        raise RuntimeError("Portal did not start")
    assert "Migration & claims review" in unescape(home)
    if full:
        assert "Both survey archives and codebooks are available." in home
    token = re.search(r'name="csrf" value="([^"]+)"', home)[1]
    try:
        get("/runs", {"kind": "claims"})
    except HTTPError as exc:
        assert exc.code == 400
    else:
        raise AssertionError("Missing CSRF token must be rejected")

    def launch(kind, **values):
        url, _ = get("/runs", {"kind": kind, "csrf": token, **values})
        return int(url.rsplit("/", 1)[1])

    def wait(job_id):
        deadline = time.monotonic() + 330
        while time.monotonic() < deadline:
            _, body = get(f"/runs/{job_id}")
            if ">SUCCEEDED</span>" in body:
                return body
            if ">FAILED</span>" in body:
                raise AssertionError(get(f"/runs/{job_id}/files/run.log")[1])
            time.sleep(2)
        raise TimeoutError(job_id)

    def evidence(job_id, name):
        return json.loads(get(f"/runs/{job_id}/files/{name}")[1])

    claims = launch("claims")
    survey = launch("survey_full" if full else "survey_fixture")
    assert "Claim outcomes" in wait(claims)
    _, claim = get(f"/runs/{claims}/claims/C002")
    assert "Filing deadline" in claim and "COVERAGE" in claim
    get(f"/runs/{claims}/claims/C002/draft", {"csrf": token})
    _, page = get(f"/runs/{claims}")
    notice = re.search(r'name="reference" value="(CL-[a-f0-9]+)"', page)[1]
    assert "Preview approved payloads" not in page
    _, page = get(f"/runs/{claims}/review", {
        "csrf": token, "reference": notice, "reviewer": "Integration reviewer",
        "note": "Verified fictional policy",
    })
    assert "Preview approved payloads" in page
    assert evidence(claims, "summary.json") == {"PASS": 2, "REVIEW": 3, "QUARANTINED": 2}
    print("Claims run, citations, approval, preview, and file downloads verified", flush=True)

    wait(survey)
    parity = evidence(survey, "reconciliation_corrected.json")
    defect = evidence(survey, "reconciliation_defect.json")
    assert (parity["status"], parity["groups"]) == ("PASS", 105 if full else 5)
    assert defect["failed_groups"] == (105 if full else 3)
    if full:
        manifest = evidence(survey, "manifest.json")
        assert [m["rows"] for m in manifest] == [433323, 457670]
        assert evidence(survey, "retrieved_evidence.json")
    assessment = launch("assessment", requirement=Path("examples/year_extension.json").read_text(),
                        manifest_id=survey)
    assert "NEEDS_CLARIFICATION" in wait(assessment)
    print("Survey parity and manifest-backed requirement assessment verified", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args()
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    with TemporaryDirectory() as state:
        proc = subprocess.Popen(
            [sys.executable, "-m", "satyasetu_portal.web", "--port", str(port), "--state", state],
            env={k: v for k, v in os.environ.items() if k != "SATYASETU_PASSWORD"},
        )
        try:
            exercise(f"http://127.0.0.1:{port}", args.full)
        finally:
            proc.send_signal(signal.SIGINT)
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


if __name__ == "__main__":
    main()
