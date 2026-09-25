"""Streaming parsers for the three raw export formats — one row/element held in
memory at a time, so multi-GB files never need to fit in RAM. Each parser yields
dicts with the same field set and Python types (str/int/float/list), ready for
argus.ingest.validate.validate_and_coerce.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterator

import ijson
from lxml import etree

from argus.ingest.schema import AMOUNT_ARRAY_FIELDS, ARRAY_FIELDS, CANONICAL_FIELDS, INT_FIELDS
from argus.synth.export import ARRAY_SEP  # must match the delimiter synth's CSV writer used


def _coerce_scalars(row: dict) -> dict:
    for field in INT_FIELDS:
        row[field] = int(row[field])
    row["fee"] = float(row["fee"])
    return row


def parse_csv(path: Path) -> Iterator[dict]:
    with open(path, "r", newline="", encoding="utf-8") as f:
        for raw in csv.DictReader(f):
            row = dict(raw)
            for field in ARRAY_FIELDS:
                parts = row[field].split(ARRAY_SEP) if row[field] else []
                row[field] = [float(p) for p in parts] if field in AMOUNT_ARRAY_FIELDS else parts
            yield _coerce_scalars(row)


def parse_json(path: Path) -> Iterator[dict]:
    with open(path, "rb") as f:
        for item in ijson.items(f, "item"):
            row = dict(item)
            for field in AMOUNT_ARRAY_FIELDS:
                row[field] = [float(v) for v in row[field]]
            yield _coerce_scalars(row)


def parse_xml(path: Path) -> Iterator[dict]:
    context = etree.iterparse(str(path), events=("end",), tag="transaction")
    for _, elem in context:
        row: dict = {}
        for field in CANONICAL_FIELDS:
            child = elem.find(field)
            if field in ARRAY_FIELDS:
                values = [item.text for item in child]
                row[field] = [float(v) for v in values] if field in AMOUNT_ARRAY_FIELDS else values
            else:
                row[field] = child.text
        yield _coerce_scalars(row)
        elem.clear()
        while elem.getprevious() is not None:
            del elem.getparent()[0]
    del context
