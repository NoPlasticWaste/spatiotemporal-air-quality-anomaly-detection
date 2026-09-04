#!/usr/bin/env python3
"""
Determine transport_supported from HYSPLIT trajectories and GFED5 fire emissions.

Example
-------
python 05_determine_transport_supported.py \
  --work-dir "/Volumes/NO NAME/hysplit-validation" \
  --gfed-stable-dir "/Volumes/NO NAME/gfed5_data/stable_2021_2022" \
  --gfed-nrt-dir "/Volumes/NO NAME/GFED5NRT"
"""

import argparse
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr


FIRE_PERCENTILE = 0.90
MIN_ABSOLUTE_EMISSION_G = 0.0
STAGNATION_KM = 100.0


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--work-dir", required=True, type=Path)
    p.add_argument("--gfed-stable-dir", required=True, type=Path,
                   help="Directory containing GFED5.1_daily_YYYY-MM.nc (2021-2022).")
    p.add_argument("--gfed-nrt-dir", required=True, type=Path,
                   help="Directory containing GFED5NRTspe_CMB_2023-MM-DD.nc.")
    p.add_argument("--output-csv", type=Path, default=None,
                   help="Optional output path; default: WORK_DIR/hysplit_validation_results_final.csv")
    return p.parse_args()


def grid_index(lat, lon):
    lat_idx = int(round((lat + 89.875) / 0.25))
    lon_idx = int(round((lon + 179.875) / 0.25))
    return max(0, min(lat_idx, 719)), max(0, min(lon_idx, 1439))


def register_fire_days(values, times, fire_days):
    values = np.asarray(values)
    if values.ndim != 3:
        raise ValueError(f"Expected 3D array, got {values.shape}")

    threshold = np.nanquantile(values, FIRE_PERCENTILE, axis=0)
    threshold = np.maximum(threshold, MIN_ABSOLUTE_EMISSION_G)

    for ti, t in enumerate(times):
        current = values[ti]
        mask = (
            np.isfinite(current)
            & (current > 0)
            & (current >= threshold)
        )
        hit_lat, hit_lon = np.where(mask)
        day = pd.Timestamp(t).strftime("%Y-%m-%d")
        for la, lo in zip(hit_lat, hit_lon):
            fire_days[(int(la), int(lo), day)] = True


def trajectory_crosses_fire(tdump_path, episode_date, fire_days):
    if not tdump_path.exists():
        return False

    lines = tdump_path.read_text().splitlines()
    idx = 0
    n_meteo = int(lines[idx].split()[0]); idx += 1 + n_meteo
    n_traj = int(lines[idx].split()[0]); idx += 1 + n_traj
    idx += 1

    window = {
        (episode_date - pd.Timedelta(days=d)).strftime("%Y-%m-%d")
        for d in (0, 1)
    }

    for line in lines[idx:]:
        p = line.split()
        if len(p) < 12:
            continue
        cell = grid_index(float(p[9]), float(p[10]))
        if any((cell[0], cell[1], day) in fire_days for day in window):
            return True
    return False


def main():
    args = parse_args()
    work_dir = args.work_dir.expanduser().resolve()
    stable_dir = args.gfed_stable_dir.expanduser().resolve()
    nrt_dir = args.gfed_nrt_dir.expanduser().resolve()

    results_csv = work_dir / "hysplit_validation_results.csv"
    tdump_dir = work_dir / "tdump"
    output_csv = (
        args.output_csv.expanduser().resolve()
        if args.output_csv else work_dir / "hysplit_validation_results_final.csv"
    )

    if not results_csv.exists():
        raise FileNotFoundError(results_csv)
    if not tdump_dir.exists():
        raise FileNotFoundError(tdump_dir)

    results = pd.read_csv(results_csv)
    results["date"] = pd.to_datetime(results["date"])
    print(f"Trajectories loaded: {len(results):,}")

    fire_days = {}

    stable_files = sorted(stable_dir.glob("GFED5.1_daily_*.nc"))
    print(f"GFED5 stable files: {len(stable_files)}")
    for path in stable_files:
        print(f"Stable: {path.name}", flush=True)
        with xr.open_dataset(path) as ds:
            if "PM2.5" not in ds.data_vars:
                raise KeyError(f"PM2.5 missing in {path.name}")
            values = ds["PM2.5"].load().values
            times = pd.to_datetime(ds["time"].values)
        register_fire_days(values, times, fire_days)
        del values

    nrt_files = sorted(nrt_dir.glob("GFED5NRTspe_CMB_2023-*.nc"))
    print(f"GFED5 NRT files: {len(nrt_files)}")
    nrt_by_month = defaultdict(list)
    for path in nrt_files:
        nrt_by_month[path.stem.split("_")[-1][:7]].append(path)

    for month, paths in sorted(nrt_by_month.items()):
        print(f"NRT: {month} ({len(paths)} days)", flush=True)
        arrays, times = [], []
        for path in sorted(paths):
            with xr.open_dataset(path) as ds:
                if "PM25" not in ds.data_vars:
                    raise KeyError(f"PM25 missing in {path.name}")
                arrays.append(ds["PM25"].isel(time=0).load().values)
                times.append(pd.to_datetime(ds["time"].values[0]))
        values = np.stack(arrays, axis=0)
        register_fire_days(values, pd.to_datetime(times), fire_days)
        del arrays, values

    print(f"Fire cell-days: {len(fire_days):,}")

    supported = []
    missing_tdump = 0
    for n, row in enumerate(results.itertuples(index=False), 1):
        tdump = tdump_dir / f"tdump_{row.location_id}_{row.date:%Y%m%d%H}"
        if not tdump.exists():
            missing_tdump += 1
        supported.append(trajectory_crosses_fire(tdump, row.date, fire_days))
        if n % 1000 == 0:
            print(f"Checked: {n:,}/{len(results):,}", flush=True)

    results["transport_supported"] = supported
    results["stagnant"] = results["trajectory_km"] < STAGNATION_KM

    cols = [
        "location_id", "date", "transport_supported", "trajectory_km",
        "stagnant", "mean_height_m", "end_lat", "end_lon",
    ]
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    results[cols].to_csv(output_csv, index=False)

    n_supported = int(results["transport_supported"].sum())
    print(f"TDUMP missing             : {missing_tdump:,}")
    print(
        f"transport_supported=True  : {n_supported:,}/{len(results):,} "
        f"({n_supported / len(results) * 100:.1f}%)"
    )
    print(f"Output: {output_csv}")


if __name__ == "__main__":
    main()
