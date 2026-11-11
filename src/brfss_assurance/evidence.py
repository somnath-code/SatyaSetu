"""Retrieve policy evidence from the supplied annual codebooks."""

import html
import re
from pathlib import Path

from .input_data import archive_member

CDC_PAGES = {
    2023: "https://www.cdc.gov/brfss/annual_data/annual_2023.html",
    2024: "https://www.cdc.gov/brfss/annual_data/annual_2024.html",
}
TOKENS = re.compile(r"[a-z0-9_]+", re.I)


def extract_codebook(path, year):
    with archive_member(path, ".html") as stream:
        raw = stream.read().decode("utf-8", errors="replace")
    documents = []
    for table in re.findall(r"<table\b.*?</table>", raw, flags=re.I | re.S):
        text = html.unescape(re.sub(r"<[^>]*>", " ", table))
        text = " ".join(text.split())
        match = re.search(r"SAS Variable Name:\s*([A-Za-z0-9_]+)", text)
        if match:
            field = match.group(1)
            documents.append({"id": f"CDC-BRFSS-{year}:{field}", "year": year,
                              "field": field, "source": CDC_PAGES[year],
                              "text": text})
    if not any(d["field"] == "DIABETE4" for d in documents):
        raise ValueError(f"No DIABETE4 table found in {Path(path).name}")
    return documents


def retrieve(documents, query, year=None, limit=3):
    words = set(TOKENS.findall(query.lower()))
    ranked = []
    for doc in documents:
        if year is not None and doc["year"] != year:
            continue
        matches = len(words & set(TOKENS.findall(doc["text"].lower())))
        if matches:
            priority = 20 if doc["field"].lower() in words else 0
            ranked.append((matches + priority, doc))
    ranked.sort(key=lambda x: (-x[0], x[1]["id"]))
    return [doc for _, doc in ranked[:limit]]
