#!/usr/bin/env python3
"""Reconstruct ordered reel-window chains from slot spin JSONL data.

The script reads `virtualreellist` windows from each spin, counts unique windows per
reel, and orders them into overlap chains where each next window is a one-symbol
shift of the previous window (i.e. suffix/prefix overlap of `window_size - 1`).
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

Window = tuple[int, ...]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reconstruct reel-window overlap chains from virtualreellist data."
    )
    parser.add_argument(
        "--input-jsonl",
        type=Path,
        default=Path("spin_data.jsonl"),
        help="Path to the JSONL file containing spin responses.",
    )
    parser.add_argument(
        "--window-size",
        type=int,
        default=7,
        help="Expected virtual reel window size used for overlap matching.",
    )
    return parser.parse_args()


def extract_virtual_reels(row: dict[str, Any]) -> list[list[int]] | None:
    response = row.get("response", row)
    if not isinstance(response, dict):
        return None

    try:
        reels = response["game"]["play"]["videoslotstate"]["virtualreellist"]
    except (KeyError, TypeError):
        return None

    if not isinstance(reels, list) or not reels:
        return None
    parsed: list[list[int]] = []
    for reel in reels:
        if not isinstance(reel, list) or not reel:
            return None
        parsed.append([int(symbol) for symbol in reel])
    return parsed


def load_reel_windows(path: Path, window_size: int) -> dict[int, Counter[Window]]:
    counts: dict[int, Counter[Window]] = defaultdict(Counter)

    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            reels = extract_virtual_reels(row)
            if reels is None:
                continue
            for reel_index, reel in enumerate(reels, start=1):
                if len(reel) != window_size:
                    raise ValueError(
                        f"Reel {reel_index} had window length {len(reel)}; expected {window_size}."
                    )
                counts[reel_index][tuple(reel)] += 1

    return counts


def build_chains(windows: Counter[Window]) -> list[list[Window]]:
    unique_windows = list(windows)
    if not unique_windows:
        return []

    prefix_map: dict[tuple[int, ...], list[Window]] = defaultdict(list)
    indegree: dict[Window, int] = {window: 0 for window in unique_windows}
    outgoing: dict[Window, list[Window]] = defaultdict(list)

    for window in unique_windows:
        prefix_map[window[:-1]].append(window)

    for window in unique_windows:
        for nxt in prefix_map.get(window[1:], []):
            outgoing[window].append(nxt)
            indegree[nxt] += 1

    starts = [window for window in unique_windows if indegree[window] == 0]
    if not starts:
        starts = sorted(unique_windows)

    visited: set[Window] = set()
    chains: list[list[Window]] = []

    for start in sorted(starts):
        if start in visited:
            continue
        chain = [start]
        visited.add(start)
        current = start

        while True:
            candidates = [candidate for candidate in sorted(outgoing[current]) if candidate not in visited]
            if not candidates:
                break
            current = candidates[0]
            chain.append(current)
            visited.add(current)

        chains.append(chain)

    for window in sorted(unique_windows):
        if window not in visited:
            chains.append([window])

    return chains


def chain_to_sequence(chain: list[Window]) -> list[int]:
    if not chain:
        return []
    sequence = list(chain[0])
    for window in chain[1:]:
        sequence.append(window[-1])
    return sequence


def format_window(window: Window) -> str:
    return "[" + ", ".join(str(symbol) for symbol in window) + "]"


def main() -> None:
    args = parse_args()
    if not args.input_jsonl.exists():
        raise FileNotFoundError(f"Input file not found: {args.input_jsonl}")

    counts = load_reel_windows(args.input_jsonl, args.window_size)
    if not counts:
        print("No virtualreellist data found.")
        return

    for reel_index in sorted(counts):
        window_counts = counts[reel_index]
        chains = build_chains(window_counts)
        print(f"Reel {reel_index}")
        print(f"  Unique partial reels: {len(window_counts)}")
        print("  Partial reels by frequency:")
        for window, frequency in sorted(window_counts.items(), key=lambda item: (-item[1], item[0])):
            print(f"    x{frequency:<3} {format_window(window)}")
        print("  Ordered overlap chains:")
        for chain_number, chain in enumerate(chains, start=1):
            sequence = chain_to_sequence(chain)
            print(f"    Chain {chain_number}: sequence {sequence}")
            for step, window in enumerate(chain, start=1):
                print(f"      {step:>2}. x{window_counts[window]:<3} {format_window(window)}")
        print()


if __name__ == "__main__":
    main()
