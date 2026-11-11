"""Command-line entry points for the demo and review workflow."""

import argparse
import csv
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path

from . import legacy
from .evidence import CDC_PAGES, extract_codebook, retrieve
from .input_data import stage
from .notify import dispatch
from .report import json_value, load_json, migration_report, save_json
from .requirements import ROLES, assess
from .tickets import Tickets
from .validation import reconcile, source_schema_diff


def source_profile(paths):
    counts = []
    distributions = []
    for path in paths:
        codes, keys, geographies = Counter(), set(), set()
        summary = dict.fromkeys(("rows", "duplicate_source_keys", "missing_geography",
                                 "null_response", "dont_know", "refused", "invalid_response",
                                 "invalid_weight", "missing_stratum", "missing_psu"), 0)
        minimum = maximum = None
        with path.open(newline="", encoding="utf-8") as stream:
            for row in csv.DictReader(stream):
                summary["survey_year"] = int(row["survey_year"])
                summary["rows"] += 1
                summary["duplicate_source_keys"] += row["source_row"] in keys
                keys.add(row["source_row"])
                if row["_STATE"]:
                    geographies.add(row["_STATE"])
                else:
                    summary["missing_geography"] += 1
                code = int(row["DIABETE4"]) if row["DIABETE4"] else None
                codes[code] += 1
                summary["null_response"] += code is None
                summary["dont_know"] += code == 7
                summary["refused"] += code == 9
                summary["invalid_response"] += code is not None and code not in {1, 2, 3, 4, 7, 9}
                weight = Decimal(row["_LLCPWT"]) if row["_LLCPWT"] else None
                summary["invalid_weight"] += weight is None or weight <= 0
                if weight is not None:
                    minimum = weight if minimum is None else min(minimum, weight)
                    maximum = weight if maximum is None else max(maximum, weight)
                summary["missing_stratum"] += not row["_STSTR"]
                summary["missing_psu"] += not row["_PSU"]
        summary.update(distinct_geographies=len(geographies), min_weight=minimum, max_weight=maximum)
        counts.append(summary)
        distributions.extend(
            {"survey_year": summary["survey_year"], "diabetes_response_code": code,
             "count": codes[code]}
            for code in sorted(codes, key=lambda code: -1 if code is None else code)
        )
    return {"summary": counts, "response_distribution": distributions}


def run_demo(args):
    from . import spark_model

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    request = load_json(args.request)
    catalog = load_json(args.catalog)
    data = [(2023, args.source_2023, args.codebook_2023),
            (2024, args.source_2024, args.codebook_2024)]
    stage_paths, manifest, documents, reference = [], [], [], []
    for year, path, codebook in data:
        if not path:
            if codebook:
                raise ValueError(f"Supply the data file for the {year} codebook")
            continue
        staged = out / "staging" / f"survey_{year}.csv"
        manifest.append(stage(path, year, staged, args.limit_per_year))
        stage_paths.append(staged)
        reference.extend(legacy.calculate(staged))
        if codebook:
            documents.extend(extract_codebook(codebook, year))
    if not stage_paths:
        raise ValueError("Supply --source-2023 and optionally --source-2024, or use --fixture")

    save_json(out / "manifest.json", manifest)
    save_json(out / "codebook_index.json", documents)
    snippets = []
    for snapshot in manifest:
        snippets.extend(retrieve(documents, "DIABETE4", year=snapshot["year"], limit=1))
    save_json(out / "retrieved_evidence.json", snippets)

    assessment = assess(request, catalog, [d["source_columns"] for d in manifest])
    active_session = spark_model.SparkSession.getActiveSession()
    spark = active_session or spark_model.build_spark(local=not args.delta_destination)
    fact = None
    published = False
    try:
        bronze = spark_model.read_bronze(spark, stage_paths)
        fact = spark_model.survey_fact(bronze).cache()
        gold = spark_model.aggregate(fact)
        correct = reconcile(reference, [row.asDict() for row in gold.collect()])
        defect = reconcile(reference, [
            row.asDict() for row in spark_model.aggregate(fact, inject_defect=True).collect()
        ])
        source = source_profile(stage_paths)
        target = spark_model.profile(fact)
        profile = {"status": "PASS" if source == target else "FAIL",
                   "source": source, "target": target}
        if (args.delta_destination and assessment["verdict"] == "SUITABLE"
                and correct["status"] == profile["status"] == "PASS"):
            spark_model.publish_delta(bronze, fact, gold, args.delta_destination)
            published = True
    finally:
        if active_session is None:
            spark.stop()
        elif fact is not None:
            fact.unpersist()

    assessment["validation_status"] = (
        "PASS" if correct["status"] == profile["status"] == "PASS"
        else "FAIL"
    )
    if args.delta_destination:
        assessment["delta_publication"] = "PUBLISHED" if published else "SKIPPED"
    scope = "Synthetic fixture" if args.fixture else "CDC source archives"
    if args.limit_per_year:
        scope += f", up to {args.limit_per_year:,} records per year (file order, QA slice)"
    diff = source_schema_diff(*manifest) if len(manifest) == 2 else None
    store = Tickets(args.ticket_db or out / "tickets.sqlite")
    for finding in assessment["findings"]:
        store.create(request, finding["code"], finding["role"], finding["message"])
    if defect["failed_groups"]:
        store.create(request, "DENOMINATOR_DEFECT", "DEVELOPER",
                     "Review the denominator correction against the failed comparison.")
        store.create(request, "RETEST_PARITY", "TESTER",
                     "Confirm the corrected target matches the same-snapshot baseline.")
    if diff and "_RFHYPE6" in diff["removed"]:
        store.create(request, "YEAR_FIELD_DRIFT", "ARCHITECT",
                     "Review the loss of _RFHYPE6 when extending dependent metrics to 2024.")
    if assessment["validation_status"] == "FAIL":
        store.create(request, "TARGET_VALIDATION_FAILED", "DEVELOPER",
                     "Investigate target profile or reconciliation mismatches.")
    if assessment["verdict"] == "SUITABLE" and assessment["validation_status"] == "PASS":
        store.create(request, "METRIC_SIGNOFF", "BI_BA",
                     "Sign off on weighted diabetes metric parity after the other reviews.")
    rows = [row for row in store.list() if row["request_id"] == request["id"]
            and row["version"] == request["version"]]
    for name, value in (
        ("assessment", assessment), ("data_profile", profile),
        ("reconciliation_corrected", correct), ("reconciliation_defect", defect),
        ("schema_drift", diff), ("tickets", rows),
        ("notification_preview", dispatch(store)),
    ):
        save_json(out / f"{name}.json", value)
    migration_report(out / "migration_report.md", assessment, correct, defect, diff,
                     rows, snippets, scope)
    print(f"Corrected: {correct['status']} ({correct['groups']} groups). "
          f"Defect: {defect['status']} ({defect['failed_groups']} mismatches). "
          f"Profile parity: {profile['status']}.")
    print(f"Report: {out / 'migration_report.md'}")
    if args.delta_destination and not published:
        print("Delta publication skipped. Review the design and validation verdicts.")
        return 1
    return 0 if assessment["validation_status"] == "PASS" else 1


def run_assessment(args):
    request = load_json(args.request)
    observed = None
    if args.manifest:
        manifest = load_json(args.manifest)
        if (not isinstance(manifest, list) or not manifest or any(
            not isinstance(item, dict)
            or not isinstance(item.get("source_columns"), list)
            or not item["source_columns"]
            or any(not isinstance(field, str) for field in item["source_columns"])
            for item in manifest
        )):
            raise ValueError("Use a manifest.json from a completed demo with source columns")
        observed = [item["source_columns"] for item in manifest]
    report = assess(request, load_json(args.catalog), observed)
    out = Path(args.out)
    store = Tickets(out / "tickets.sqlite")
    report["tickets"] = [
        store.create(request, finding["code"], finding["role"], finding["message"])
        for finding in report["findings"]
    ]
    save_json(out / "intake_assessment.json", report)
    return show(report)


def show(value):
    print(json.dumps(value, default=json_value, indent=2))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="brfss")
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo", help="Run source profiling and Spark reconciliation")
    demo.add_argument("--fixture", action="store_true")
    demo.add_argument("--source-2023")
    demo.add_argument("--source-2024")
    demo.add_argument("--codebook-2023")
    demo.add_argument("--codebook-2024")
    demo.add_argument("--limit-per-year", type=int)
    demo.add_argument("--request", default="examples/migration.json")
    demo.add_argument("--catalog", default="config/catalog.json")
    demo.add_argument("--delta-destination", help="Existing Unity Catalog catalog.schema")
    demo.add_argument("--ticket-db", help="Optional SQLite path on a local filesystem")
    demo.add_argument("--out", default="out/demo")

    intake = commands.add_parser("assess", help="Assess a versioned change or migration request")
    intake.add_argument("--request", required=True)
    intake.add_argument("--catalog", default="config/catalog.json")
    intake.add_argument("--manifest", help="Use actual schema metadata from a demo run")
    intake.add_argument("--out", default="out/intake")

    listing = commands.add_parser("tickets", help="List review tickets")
    listing.add_argument("--out", default="out/demo")
    listing.add_argument("--ticket-db", help="Use the same SQLite path as the demo")
    notify = commands.add_parser("notify", help="Preview or send review notifications")
    notify.add_argument("--out", default="out/demo")
    notify.add_argument("--ticket-db", help="Use the same SQLite path as the demo")
    notify.add_argument("--send", action="store_true")
    decision = commands.add_parser("decide", help="Record a local review decision")
    decision.add_argument("ticket")
    decision.add_argument("--role", choices=ROLES, required=True)
    decision.add_argument("--actor", required=True)
    decision.add_argument("--decision", choices=["APPROVED", "REJECTED", "CHANGES_REQUESTED"],
                          required=True)
    decision.add_argument("--note", required=True)
    decision.add_argument("--out", default="out/demo")
    decision.add_argument("--ticket-db", help="Use the same SQLite path as the demo")
    evidence = commands.add_parser("evidence", help="Retrieve matching CDC codebook entries")
    evidence.add_argument("query")
    evidence.add_argument("--year", type=int, choices=CDC_PAGES)
    evidence.add_argument("--out", default="out/demo")
    args = parser.parse_args(argv)
    try:
        if args.command == "demo":
            if args.limit_per_year is not None and args.limit_per_year < 1:
                raise ValueError("--limit-per-year must be positive")
            if args.fixture:
                if args.source_2023 or args.source_2024 or args.codebook_2023 or args.codebook_2024:
                    raise ValueError("Choose fixture or CDC inputs")
                args.source_2023 = "data/sample/survey_2023.csv"
                args.source_2024 = "data/sample/survey_2024.csv"
            return run_demo(args)
        if args.command == "assess":
            return run_assessment(args)
        if args.command == "evidence":
            index = load_json(Path(args.out) / "codebook_index.json")
            return show(retrieve(index, args.query, year=args.year))
        store = Tickets(args.ticket_db or Path(args.out) / "tickets.sqlite")
        if args.command == "tickets":
            return show(store.list())
        if args.command == "notify":
            results = dispatch(store, send=args.send)
            show(results)
            return int(any(result["mode"] == "CHECK_DELIVERY" for result in results))
        store.decide(args.ticket, args.role, args.actor, args.decision, args.note)
        return show({"ticket": args.ticket, "decision": args.decision})
    except (ValueError, OSError) as exc:
        parser.exit(2, f"brfss: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
