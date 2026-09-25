"""Exports the (possibly corrupted) transaction dataset to CSV, JSON and XML — the
three raw formats the ingestion phase must all parse into the same canonical schema
— plus the clean ground_truth/entities.parquet artifact.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

import pandas as pd
from lxml import etree

from argus.synth.entities import Entity
from argus.synth.wallets import Wallet

FIELDS = [
    "txid",
    "timestamp",
    "src_ip",
    "dst_ip",
    "src_port",
    "dst_port",
    "geo_country",
    "asn",
    "input_addresses",
    "input_amounts",
    "output_addresses",
    "output_amounts",
    "fee",
    "script_type",
]
ARRAY_FIELDS = {"input_addresses", "input_amounts", "output_addresses", "output_amounts"}
ARRAY_SEP = "|"  # CSV has no native array type; ingestion must split on this separator


def _scalar(value):
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def write_csv(transactions: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(FIELDS)
        for row in transactions:
            cells = []
            for field in FIELDS:
                value = row[field]
                if field in ARRAY_FIELDS:
                    cells.append(ARRAY_SEP.join(str(v) for v in value))
                else:
                    cells.append(_scalar(value))
            writer.writerow(cells)


def write_json(transactions: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serializable = [{field: _scalar(row[field]) for field in FIELDS} for row in transactions]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2)


def write_xml(transactions: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    root = etree.Element("transactions")
    for row in transactions:
        tx_el = etree.SubElement(root, "transaction")
        for field in FIELDS:
            value = row[field]
            if field in ARRAY_FIELDS:
                container = etree.SubElement(tx_el, field)
                item_tag = "address" if "address" in field else "amount"
                for v in value:
                    item_el = etree.SubElement(container, item_tag)
                    item_el.text = str(v)
            else:
                field_el = etree.SubElement(tx_el, field)
                field_el.text = str(_scalar(value))
    tree = etree.ElementTree(root)
    tree.write(str(path), xml_declaration=True, encoding="utf-8", pretty_print=True)


def write_ground_truth_entities(wallets: list[Wallet], entities: list[Entity], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    entities_by_id = {e.entity_id: e for e in entities}
    df = pd.DataFrame(
        [
            {
                "wallet_id": w.wallet_id,
                "entity_id": w.entity_id,
                "entity_type": entities_by_id[w.entity_id].entity_type,
            }
            for w in wallets
        ]
    )
    df.to_parquet(path, index=False)
