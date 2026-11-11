"""Run the claims pipeline and review its outputs."""

import argparse
import json
from pathlib import Path

from healthcare.notifications.dispatcher import Outbox, dispatch
from healthcare.rag.retrieve import for_rules, search

DEFAULT_DATA = "data/sample/claims"
DEFAULT_OUT = "out/claims"


def lookup(out, claim_id):
    files = sorted((Path(out) / "gold/reviews").glob("part-*.json"))
    if not files:
        raise ValueError("Run claims demo to generate the review output")
    for path in files:
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                row = json.loads(line)
                if row["claim_id"] == claim_id:
                    return row
    raise ValueError(f"No claim named {claim_id}")


def policy_index(out):
    return json.loads((Path(out) / "policy_index.json").read_text(encoding="utf-8"))


def run_demo(data_dir, out):
    from pyspark.sql import SparkSession

    from brfss_assurance.spark_model import build_spark
    from healthcare.pipelines import bronze, gold, silver
    from healthcare.quality.checks import check_source_keys
    from healthcare.rag.build_index import build

    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    build(Path(data_dir) / "policies/fictional-claims-policy.md", out / "policy_index.json")
    active = SparkSession.getActiveSession()
    spark = active or build_spark(local=True)
    cached = []
    try:
        tables = bronze.load(spark, data_dir)
        check_source_keys(tables)
        clean = silver.prepare(tables).cache()
        cached.append(clean)
        reviews = gold.review(clean).cache()
        cached.append(reviews)
        for name, table in tables.items():
            table.write.mode("overwrite").parquet(str(out / "bronze" / name))
        clean.write.mode("overwrite").parquet(str(out / "silver/claim_context"))
        reviews.write.mode("overwrite").json(str(out / "gold/reviews"))
        summary = {r["status"]: r["claims"] for r in gold.summarize(reviews).collect()}
        (out / "summary.json").write_text(json.dumps(summary, sort_keys=True, indent=2) + "\n")
        return {"counts": summary, "reviews": str(out / "gold/reviews")}
    finally:
        if active is None:
            spark.stop()
        else:
            for frame in cached:
                frame.unpersist()


def explain(out, claim_id):
    row = lookup(out, claim_id)
    codes = row["review_reasons"]
    if row["status"] == "QUARANTINED":
        codes = ["QUALITY"]
    return {"claim": row, "evidence": for_rules(policy_index(out), codes)}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="claims")
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo", help="Run the synthetic claims pipeline")
    demo.add_argument("--data", default=DEFAULT_DATA)
    for name in ("explain", "draft"):
        commands.add_parser(name).add_argument("claim_id")
    commands.add_parser("search").add_argument("query")
    commands.add_parser("outbox")
    approve = commands.add_parser("approve")
    approve.add_argument("id")
    approve.add_argument("--reviewer", required=True)
    approve.add_argument("--note", required=True)
    commands.add_parser("notify").add_argument("--send", action="store_true")
    for command in commands.choices.values():
        command.add_argument("--out", default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    try:
        out = Path(args.out)
        if args.command == "demo":
            result = run_demo(args.data, out)
        elif args.command == "explain":
            result = explain(out, args.claim_id)
        elif args.command == "search":
            result = search(policy_index(out), args.query)
        else:
            queue = Outbox(out / "claims_outbox.sqlite")
            if args.command == "draft":
                result = {"id": queue.draft(lookup(out, args.claim_id))}
            elif args.command == "approve":
                queue.approve(args.id, args.reviewer, args.note)
                result = {"id": args.id, "state": "APPROVED"}
            elif args.command == "outbox":
                result = queue.list()
            else:
                result = dispatch(queue, args.send)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if args.command == "notify" and any(r["mode"] == "CHECK_DELIVERY" for r in result):
            return 1
        return 0
    except (ValueError, OSError) as exc:
        parser.exit(2, f"claims: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
