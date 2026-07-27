"""Helpers for analysing canonical PsyNet export archives."""

from __future__ import annotations

import json
import zipfile
from typing import Optional, Union

import pandas as pd


def load_export_table(
    database_zip: str,
    table: str,
) -> pd.DataFrame:
    """Load a physical table CSV from ``database.zip``.

    Parameters
    ----------
    database_zip :
        Path to the exported ``database.zip``.
    table :
        Physical table name (for example ``trial`` or ``participant``).
    """
    member = f"data/{table}.csv"
    with zipfile.ZipFile(database_zip, "r") as archive:
        with archive.open(member) as handle:
            return pd.read_csv(handle)


def unpack_json_column(
    data_frame: pd.DataFrame,
    column: str,
    *,
    prefix: Optional[str] = None,
    overwrite: bool = False,
) -> pd.DataFrame:
    """Unpack a JSON text column into ordinary columns.

    Nested objects are left as Python objects after ``json.loads``. Existing
    columns are never overwritten unless ``overwrite`` is true.
    """
    if column not in data_frame.columns:
        raise KeyError(column)

    parsed = []
    for value in data_frame[column]:
        if pd.isna(value) or value == "":
            parsed.append({})
            continue
        if isinstance(value, (dict, list)):
            parsed.append(value if isinstance(value, dict) else {"value": value})
            continue
        try:
            loaded = json.loads(value)
        except (TypeError, json.JSONDecodeError):
            parsed.append({})
            continue
        if isinstance(loaded, dict):
            parsed.append(loaded)
        else:
            parsed.append({"value": loaded})

    unpacked = pd.json_normalize(parsed)
    if prefix:
        unpacked = unpacked.add_prefix(prefix)

    result = data_frame.copy()
    for col in unpacked.columns:
        if col in result.columns and not overwrite:
            continue
        result[col] = unpacked[col].values
    return result


def merge_participant_identifiers(
    data_frame: pd.DataFrame,
    identifiers: Union[str, pd.DataFrame],
    *,
    on: str = "participant_id",
    suffixes: tuple[str, str] = ("", "_identifier"),
) -> pd.DataFrame:
    """Merge original participant identifiers onto an analysis frame.

    Parameters
    ----------
    data_frame :
        Table that contains ``participant_id`` (or another join key).
    identifiers :
        Path to ``participant_identifiers.csv`` or an already-loaded frame.
    on :
        Join column name.
    """
    if isinstance(identifiers, str):
        identifiers = pd.read_csv(identifiers)
    return data_frame.merge(identifiers, on=on, how="left", suffixes=suffixes)
