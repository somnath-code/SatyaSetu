"""Measure retrieval accuracy against known fictional policy questions."""

import argparse
import json
from pathlib import Path

from healthcare.cli import policy_index
from healthcare.rag.retrieve import search


def evaluate(out, questions):
    cases = [json.loads(line) for line in Path(questions).read_text().splitlines() if line.strip()]
    if not cases:
        raise ValueError("Provide at least one evaluation question")
    index = policy_index(out)
    correct = 0
    for case in cases:
        hits = search(index, case["query"], limit=1)
        actual = hits[0]["rule"] if hits else None
        correct += actual == case["expect"]
        print(f"{case['query']}: {actual} (expected {case['expect']})")
    print(f"Top-1 policy retrieval: {correct}/{len(cases)}")
    return 0 if correct == len(cases) else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="out/claims")
    parser.add_argument("--questions", default="evaluation/questions.jsonl")
    args = parser.parse_args()
    raise SystemExit(evaluate(args.out, args.questions))
