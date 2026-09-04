#!/usr/bin/env python3
"""Filter master HYSPLIT results to a newer/relevant request list."""

import argparse
from pathlib import Path
import pandas as pd


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--results", required=True, type=Path,
                   help="Master hysplit_validation_results_final.csv")
    p.add_argument("--requests", required=True, type=Path,
                   help="New/relevant hysplit_validation_requests.csv")
    p.add_argument("--output", required=True, type=Path,
                   help="Filtered output CSV")
    return p.parse_args()


def main():
    args = parse_args()
    results = pd.read_csv(args.results.expanduser())
    requests = pd.read_csv(args.requests.expanduser())

    results["date"] = pd.to_datetime(results["date"])
    requests["hour"] = pd.to_datetime(
        requests["hour"], utc=True
    ).dt.tz_localize(None)

    results["location_id"] = results["location_id"].astype(str).str.strip()
    requests["location_id"] = requests["location_id"].astype(str).str.strip()

    valid_keys = set(zip(requests["location_id"], requests["hour"]))
    result_keys = set(zip(results["location_id"], results["date"]))

    mask = [
        (lid, d) in valid_keys
        for lid, d in zip(results["location_id"], results["date"])
    ]
    filtered = results.loc[mask].copy()
    missing = valid_keys - result_keys

    print(f"Master results          : {len(results):,}")
    print(f"Relevant requests       : {len(requests):,}")
    print(f"Filtered results        : {len(filtered):,}")
    print(f"Requests not found      : {len(missing):,}")

    if "transport_supported" in filtered.columns:
        n_true = int(filtered["transport_supported"].eq(True).sum())
        pct = 100 * n_true / len(filtered) if len(filtered) else 0
        print(f"transport_supported=True: {n_true:,} ({pct:.1f}%)")

    out = args.output.expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    filtered.to_csv(out, index=False)
    print(f"Output: {out}")


if __name__ == "__main__":
    main()
