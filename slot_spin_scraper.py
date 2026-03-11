#!/usr/bin/env python3
"""Simple slot spin scraper for Mystic Fortune backend traffic."""

from __future__ import annotations

import argparse
import csv
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_ENDPOINT = "https://gs-test.insvr.com/pf?client=1.1.18838.1004"
DEFAULT_HEADERS = {
    "accept": "application/json",
    "content-type": "application/json",
    "origin": "https://app-test.insvr.com",
    "referer": "https://app-test.insvr.com/",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/145.0.0.0 Safari/537.36"
    ),
}

SUMMARY_KEYS = {
    "balance",
    "credit",
    "bet",
    "totalbet",
    "win",
    "totalwin",
    "freespins",
    "multiplier",
    "roundid",
    "spinid",
    "gamestate",
}
SUMMARY_KEYS_LOWER = {k.lower() for k in SUMMARY_KEYS}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replay slot spin requests and capture spin result data."
    )
    parser.add_argument("--payload-file", type=Path, required=True, help="Path to JSON payload captured from browser devtools.")
    parser.add_argument("--spins", type=int, default=25, help="Number of POST calls to send.")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT, help="Spin endpoint URL.")
    parser.add_argument("--delay", type=float, default=0.3, help="Delay in seconds between spins.")
    parser.add_argument("--timeout", type=float, default=15.0, help="HTTP timeout in seconds.")
    parser.add_argument("--output-jsonl", type=Path, default=Path("spin_data.jsonl"))
    parser.add_argument("--output-csv", type=Path, default=Path("spin_summary.csv"))
    return parser.parse_args()


def load_payload(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("Payload must be a JSON object.")
    return data


def flatten_summary(obj: Any, prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    if isinstance(obj, dict):
        for key, value in obj.items():
            key_str = str(key)
            full_key = f"{prefix}.{key_str}" if prefix else key_str
            if key_str.lower() in SUMMARY_KEYS_LOWER:
                out[full_key] = value
            out.update(flatten_summary(value, full_key))
    elif isinstance(obj, list):
        for idx, value in enumerate(obj):
            list_key = f"{prefix}[{idx}]" if prefix else f"[{idx}]"
            out.update(flatten_summary(value, list_key))
    return out


def post_json(endpoint: str, payload: dict[str, Any], timeout: float) -> tuple[int, Any]:
    raw = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(endpoint, data=raw, method="POST")
    for k, v in DEFAULT_HEADERS.items():
        req.add_header(k, v)

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        status = resp.status
        body = json.loads(resp.read().decode("utf-8"))
    return status, body


def record_spin(endpoint: str, payload: dict[str, Any], timeout: float, spin_no: int) -> dict[str, Any]:
    status_code, body = post_json(endpoint, payload, timeout)
    summary = flatten_summary(body)
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "spin": spin_no,
        "status_code": status_code,
        "summary": summary,
        "response": body,
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = ["timestamp", "spin", "status_code"]
    summary_keys: set[str] = set()
    for row in rows:
        summary_keys.update(row["summary"].keys())

    fieldnames.extend(sorted(summary_keys))
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            out = {
                "timestamp": row["timestamp"],
                "spin": row["spin"],
                "status_code": row["status_code"],
            }
            out.update(row["summary"])
            writer.writerow(out)


def main() -> None:
    args = parse_args()
    payload = load_payload(args.payload_file)

    rows: list[dict[str, Any]] = []
    for spin in range(1, args.spins + 1):
        try:
            row = record_spin(args.endpoint, payload, args.timeout, spin)
            rows.append(row)
            print(f"spin={spin:03d} status={row['status_code']} summary_fields={len(row['summary'])}")
        except urllib.error.HTTPError as exc:
            print(f"spin={spin:03d} failed: HTTP {exc.code} {exc.reason}")
        except Exception as exc:
            print(f"spin={spin:03d} failed: {exc}")

        if spin < args.spins:
            time.sleep(args.delay)

    if rows:
        write_jsonl(args.output_jsonl, rows)
        write_csv(args.output_csv, rows)
        print(f"Saved {len(rows)} spins to {args.output_jsonl} and {args.output_csv}")
    else:
        print("No successful responses captured.")


if __name__ == "__main__":
    main()
