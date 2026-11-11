"""Convert only the selected source fields to a portable staging CSV."""

import csv
import hashlib
import math
from contextlib import contextmanager
from pathlib import Path
from zipfile import ZipFile

SOURCE_FIELDS = ("_STATE", "DIABETE4", "_LLCPWT", "_STSTR", "_PSU")
STAGE_FIELDS = ("survey_year", "source_row", *SOURCE_FIELDS)


@contextmanager
def archive_member(path, suffix):
    path = Path(path)
    if path.suffix.lower() != ".zip":
        with path.open("rb") as stream:
            yield stream
        return
    with ZipFile(path) as archive:
        matches = [name for name in archive.namelist() if name.rstrip().lower().endswith(suffix)]
        if len(matches) != 1:
            raise ValueError(f"{path.name} must contain exactly one {suffix} file")
        with archive.open(matches[0]) as stream:
            yield stream


def file_sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


@contextmanager
def source_rows(path):
    """Yield source column names and a streaming iterator of projected rows."""
    if Path(path).suffix.lower() == ".csv":
        with Path(path).open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            yield list(reader.fieldnames or ()), reader
        return
    import pandas as pd

    with archive_member(path, ".xpt") as stream:
        # A ZipExtFile can seek, but backwards seeks repeatedly decompress.
        # Spool the archive member to disk for predictable full-file scan time.
        from tempfile import TemporaryFile
        from shutil import copyfileobj

        with TemporaryFile() as uncompressed:
            copyfileobj(stream, uncompressed)
            uncompressed.seek(0)
            with pd.read_sas(uncompressed, format="xport", chunksize=5000) as reader:
                columns = [c.decode("ascii") if isinstance(c, bytes) else c
                           for c in reader.columns]

                def records():
                    for frame in reader:
                        frame.columns = columns
                        yield from frame[list(SOURCE_FIELDS)].to_dict("records")

                yield columns, records()


def normalize(value, *, integer):
    if value is None or value == "":
        return ""
    number = float(value)
    if not math.isfinite(number):
        return ""
    if integer:
        if not number.is_integer():
            raise ValueError(f"Expected integer source code, received {number}")
        return str(int(number))
    return f"{number:.8f}"


def stage(path, year, output, limit=None):
    from itertools import islice

    columns, row_count = [], 0
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with source_rows(path) as (columns, rows):
        missing = set(SOURCE_FIELDS) - set(columns)
        if missing:
            raise ValueError(f"Missing source fields for {year}: {sorted(missing)}")
        with output.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(STAGE_FIELDS)
            for row_count, row in enumerate(islice(rows, limit), start=1):
                values = [normalize(row[field], integer=field != "_LLCPWT")
                          for field in SOURCE_FIELDS]
                writer.writerow((year, row_count, *values))
    if not row_count:
        raise ValueError(f"Source for {year} contained no records")
    return {
        "year": year, "file": Path(path).name, "sha256": file_sha256(path),
        "rows": row_count, "limit_per_year": limit, "source_columns": sorted(columns),
    }
