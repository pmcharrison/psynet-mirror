"""Load the committed arithmetic item bank."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

ITEM_BANK_PATH = Path(__file__).resolve().parent / "stimuli" / "item_bank.json"


@lru_cache(maxsize=1)
def load_item_bank() -> tuple[dict, ...]:
    """Return the calibrated item bank as an immutable sequence of dicts."""
    items = json.loads(ITEM_BANK_PATH.read_text())
    return tuple(items)


def item_by_id() -> dict[str, dict]:
    """Return items keyed by ``item_id``."""
    return {item["item_id"]: item for item in load_item_bank()}
