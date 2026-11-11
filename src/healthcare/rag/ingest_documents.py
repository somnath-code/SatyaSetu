"""Split a Markdown policy into cited sections using its rule headings."""

import re
from pathlib import Path

HEADER = re.compile(r"^## ([A-Z_]+) — (.+)$", re.M)


def load_policy(path):
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    sections = list(HEADER.finditer(text))
    if not sections:
        raise ValueError(f"No policy sections found in {path.name}")
    docs = {}
    for i, section in enumerate(sections):
        code, title = section.groups()
        if code in docs:
            raise ValueError(f"Duplicate policy section {code}")
        end = sections[i+1].start() if i+1 < len(sections) else len(text)
        body = text[section.end():end].strip()
        if not body:
            raise ValueError(f"Empty policy section {code}")
        docs[code] = {"rule": code, "title": title, "text": body,
                      "citation": f"{path.name} § {code}"}
    return docs
