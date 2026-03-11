# SimpleScraper

A lightweight scraper to collect spin data for the Mystic Fortune slot backend
without driving the website UI.

## What this does

It replays the POST request to:

- `https://gs-test.insvr.com/pf?client=1.1.18838.1004`

and stores each response as:

- full JSON record in `spin_data.jsonl`
- flattened summary fields in `spin_summary.csv`

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Capture your payload once

In browser devtools (Network tab), find the same `POST /pf?...` request and copy
its **Request Payload** into a local file, for example `payload.json`.

> The exact payload usually includes session/game state values and is required.

## Run

```bash
python3 slot_spin_scraper.py --payload-file payload.json --spins 100 --delay 0.25
```

Optional flags:

- `--output-jsonl my_spins.jsonl`
- `--output-csv my_spins.csv`
- `--timeout 20`

## Output example

Console output:

```text
spin=001 status=200 summary_fields=14
spin=002 status=200 summary_fields=13
...
Saved 100 spins to spin_data.jsonl and spin_summary.csv
```
