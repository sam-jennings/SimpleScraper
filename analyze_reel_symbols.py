#!/usr/bin/env python3
"""Build cumulative symbol frequencies per reel from spin_data.jsonl."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a cumulative symbol frequency table for each reel."
    )
    parser.add_argument(
        "--input-jsonl",
        type=Path,
        default=Path("spin_data.jsonl"),
        help="Path to spin_data.jsonl",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("reel_symbol_frequency.csv"),
        help="Output CSV for cumulative symbol counts by reel.",
    )
    return parser.parse_args()


def is_scalar(value: Any) -> bool:
    return isinstance(value, (str, int, float, bool)) or value is None


def _list_of_scalar_lists(value: Any) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(row, list) and row and all(is_scalar(x) for x in row) for row in value)
    )


def _dict_list_to_reels(value: Any) -> list[list[Any]] | None:
    if not isinstance(value, list) or not value:
        return None
    reels: list[list[Any]] = []
    for item in value:
        if not isinstance(item, dict):
            return None
        symbols = item.get("symbols")
        if not (isinstance(symbols, list) and symbols and all(is_scalar(x) for x in symbols)):
            return None
        reels.append(symbols)
    return reels if reels else None


def _reellist_to_names(value: Any) -> list[list[str]] | None:
    """Convert videoslot `reellist` objects into reel symbol-name rows.

    Expected shape:
    [
      {"symbols": {"symbol": [{"name": "A"}, ...]}},
      ...
    ]
    """
    if not isinstance(value, list) or not value:
        return None

    reels: list[list[str]] = []
    for item in value:
        if not isinstance(item, dict):
            return None

        symbols = item.get("symbols")
        if isinstance(symbols, dict):
            symbol_list = symbols.get("symbol")
        else:
            symbol_list = symbols

        if not isinstance(symbol_list, list) or not symbol_list:
            return None

        names: list[str] = []
        for symbol in symbol_list:
            if isinstance(symbol, dict) and "name" in symbol:
                names.append(str(symbol["name"]))
            elif is_scalar(symbol):
                names.append(str(symbol))
            else:
                return None

        if not names:
            return None
        reels.append(names)

    return reels if reels else None


def find_reel_grid(response: Any) -> list[list[Any]] | None:
    candidates: list[tuple[int, list[list[Any]]]] = []

    def walk(node: Any, path: str = "") -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                key_path = f"{path}.{key}" if path else str(key)
                lower_key = str(key).lower()

                if _list_of_scalar_lists(value):
                    outer_len = len(value)
                    inner_len = max(len(x) for x in value)
                    score = outer_len * inner_len
                    if "reel" in lower_key:
                        score += 100
                    if "symbol" in lower_key:
                        score += 60
                    if "screen" in lower_key or "window" in lower_key:
                        score += 40
                    if "virtual" in lower_key:
                        score -= 120
                    candidates.append((score, value))

                reels = _dict_list_to_reels(value)
                if reels is not None:
                    score = len(reels) * max(len(x) for x in reels) + 80
                    if "reel" in lower_key:
                        score += 100
                    candidates.append((score, reels))

                reels = _reellist_to_names(value)
                if reels is not None:
                    score = len(reels) * max(len(x) for x in reels) + 220
                    if "reel" in lower_key:
                        score += 100
                    candidates.append((score, reels))

                walk(value, key_path)

        elif isinstance(node, list):
            for idx, item in enumerate(node):
                walk(item, f"{path}[{idx}]")

    walk(response)
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def load_counts(path: Path) -> tuple[dict[int, Counter[str]], int, int]:
    counts: dict[int, Counter[str]] = defaultdict(Counter)
    processed = 0
    matched = 0

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            processed += 1
            row = json.loads(line)
            response = row.get("response", row) if isinstance(row, dict) else row
            grid = find_reel_grid(response)
            if grid is None:
                continue

            matched += 1
            for reel_index, reel in enumerate(grid, start=1):
                for symbol in reel:
                    counts[reel_index][str(symbol)] += 1

    return counts, processed, matched


def write_frequency_csv(path: Path, counts: dict[int, Counter[str]]) -> None:
    reel_ids = sorted(counts.keys())
    symbols = sorted({symbol for c in counts.values() for symbol in c})

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["symbol", *[f"reel_{idx}" for idx in reel_ids], "total"])

        for symbol in symbols:
            row_counts = [counts[idx].get(symbol, 0) for idx in reel_ids]
            writer.writerow([symbol, *row_counts, sum(row_counts)])


def main() -> None:
    args = parse_args()
    if not args.input_jsonl.exists():
        raise FileNotFoundError(f"Input file not found: {args.input_jsonl}")

    counts, processed, matched = load_counts(args.input_jsonl)
    if not counts:
        print("No reel/symbol arrays found in the input file.")
        return

    write_frequency_csv(args.output_csv, counts)
    print(
        f"Processed {processed} rows, matched {matched} rows with reel data. "
        f"Saved table to {args.output_csv}"
    )


if __name__ == "__main__":
    main()
