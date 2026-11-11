"""Generate deterministic synthetic claim records in a separate directory."""

import argparse
import csv
import random
from pathlib import Path
from shutil import copyfile


def write(path, header, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        writer.writerows(rows)


def generate(out, count, seed):
    rng = random.Random(seed)
    out.mkdir(parents=True, exist_ok=True)
    write(out / "patients.csv", ("patient_id", "plan_id"),
          ((f"P{i:05}", rng.choice(["BASIC", "PLUS"])) for i in range(count)))
    write(out / "encounters.csv", ("encounter_id", "patient_id", "service_code", "service_date"),
          ((f"E{i:05}", f"P{i:05}", rng.choice(["VISIT", "LAB", "IMAGE"]), "2026-01-01")
           for i in range(count)))
    write(out / "claims.csv", ("claim_id", "encounter_id", "billed_cents", "submitted_on"),
          ((f"C{i:05}", f"E{i:05}", rng.randint(1, 120000),
            rng.choice(["2026-01-03", "2026-02-03"])) for i in range(count)))
    policy = Path(__file__).resolve().parents[1] / "data/sample/claims/policies/fictional-claims-policy.md"
    destination = out / "policies" / policy.name
    destination.parent.mkdir(exist_ok=True)
    copyfile(policy, destination)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("out/generated-claims"))
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    if args.count < 1:
        parser.error("--count must be positive")
    generate(args.out, args.count, args.seed)
