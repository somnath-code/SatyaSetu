"""Retrieve cited policy sections by claim rule or a text query."""

import re

TOKEN = re.compile(r"[a-z0-9_]+")


def for_rules(index, rule_ids):
    return [index[rule] for rule in rule_ids]


def search(index, query, limit=3):
    terms = set(TOKEN.findall(query.lower()))
    ranked = []
    for key, doc in index.items():
        words = set(TOKEN.findall(f"{key} {doc['title']} {doc['text']}".lower()))
        score = len(terms & words) + (10 if key.lower() in terms else 0)
        if score:
            ranked.append((-score, key))
    return [index[key] for _, key in sorted(ranked)[:limit]]
