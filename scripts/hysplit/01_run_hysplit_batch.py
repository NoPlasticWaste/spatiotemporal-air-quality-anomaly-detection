#!/usr/bin/env python3
"""
Run local HYSPLIT backward trajectories for irregular episode timestamps.

Example
-------
python 04_run_hysplit_batch.py \
  --hysplit-exec ~/hysplit/exec/hyts_std \
  --work-dir "/Volumes/NO NAME/hysplit-validation" \
  --requests-csv data/processed/hysplit_validation_requests.csv

Notes
-----
- Writes HYSPLIT CONTROL files directly because episode timestamps are irregular.
- Streams GDAS1 weekly files: download -> process -> remove when no longer needed.
- Includes a +3 hour meteorological buffer so starts at 22/23 UTC on GDAS file
  boundaries can be initialized correctly.
"""

import argparse
import gc
import subprocess
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd


GDAS_BASE_URL = "https://www.ready.noaa.gov/data/archives/gdas1/"
RUNTIME_HOURS = -24
START_HEIGHT_M = 100.0
MODEL_TOP_M = 10000.0


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--hysplit-exec", required=True, type=Path,
                   help="Path to HYSPLIT hyts_std executable.")
    p.add_argument("--work-dir", required=True, type=Path,
                   help="Working directory for CONTROL, meteo, tdump and results.")
    p.add_argument("--requests-csv", required=True, type=Path,
                   help="CSV containing irregular trajectory requests.")
    return p.parse_args()


def gdas_week_file(ts: pd.Timestamp) -> str:
    week = min((ts.day - 1) // 7 + 1, 5)
    return f"gdas1.{ts.strftime('%b').lower()}{ts.strftime('%y')}.w{week}"


def required_week_files(ts: pd.Timestamp) -> list[str]:
    """Files needed for -24 h trajectory + start-time interpolation buffer."""
    times = [
        ts + pd.Timedelta(hours=RUNTIME_HOURS),
        ts,
        ts + pd.Timedelta(hours=3),
    ]
    files = []
    for t in times:
        f = gdas_week_file(t)
        if f not in files:
            files.append(f)
    return files


def download_gdas(filename: str, meteo_dir: Path) -> Path:
    """Download safely to .part, then rename only after completion."""
    target = meteo_dir / filename
    if target.exists():
        return target

    part = meteo_dir / f"{filename}.part"
    part.unlink(missing_ok=True)
    url = GDAS_BASE_URL + filename

    print(f"    downloading {filename} ...", flush=True)
    urllib.request.urlretrieve(url, part)
    part.replace(target)

    print(f"    done ({target.stat().st_size / 1e9:.2f} GB)", flush=True)
    return target


def write_control(episode, meteo_files, tdump_name, work_dir, meteo_dir, tdump_dir):
    ts = episode.hour_ts
    lines = [
        ts.strftime("%y %m %d %H"),
        "1",
        f"{episode.latitude:.4f} {episode.longitude:.4f} {START_HEIGHT_M:.1f}",
        str(RUNTIME_HOURS),
        "0",
        f"{MODEL_TOP_M:.1f}",
        str(len(meteo_files)),
    ]
    for f in meteo_files:
        lines += [f"{meteo_dir}/", f]
    lines += [f"{tdump_dir}/", tdump_name]
    (work_dir / "CONTROL").write_text("\n".join(lines) + "\n")


def parse_tdump(path: Path):
    if not path.exists():
        return None
    lines = path.read_text().splitlines()
    try:
        idx = 0
        n_meteo = int(lines[idx].split()[0])
        idx += 1 + n_meteo
        n_traj = int(lines[idx].split()[0])
        idx += 1 + n_traj
        idx += 1
    except (IndexError, ValueError):
        return None

    rows = []
    for line in lines[idx:]:
        p = line.split()
        if len(p) >= 12:
            rows.append({
                "age_hours": float(p[8]),
                "lat": float(p[9]),
                "lon": float(p[10]),
                "height_m": float(p[11]),
            })
    return pd.DataFrame(rows) if rows else None


def trajectory_length_km(traj):
    R = 6371.0
    lat = np.radians(traj["lat"].to_numpy())
    lon = np.radians(traj["lon"].to_numpy())
    dlat = np.diff(lat)
    dlon = np.diff(lon)
    a = np.sin(dlat / 2) ** 2 + np.cos(lat[:-1]) * np.cos(lat[1:]) * np.sin(dlon / 2) ** 2
    return float((2 * R * np.arcsin(np.sqrt(np.clip(a, 0, 1)))).sum())


def main():
    args = parse_args()
    hysplit_exec = args.hysplit_exec.expanduser().resolve()
    work_dir = args.work_dir.expanduser().resolve()
    requests_csv = args.requests_csv.expanduser().resolve()

    meteo_dir = work_dir / "meteo"
    tdump_dir = work_dir / "tdump"
    results_csv = work_dir / "hysplit_validation_results.csv"

    for d in (work_dir, meteo_dir, tdump_dir):
        d.mkdir(parents=True, exist_ok=True)

    if not hysplit_exec.exists():
        raise FileNotFoundError(f"hyts_std not found: {hysplit_exec}")
    if not requests_csv.exists():
        raise FileNotFoundError(f"requests CSV not found: {requests_csv}")

    requests = pd.read_csv(requests_csv)
    requests["location_id"] = requests["location_id"].astype(str)
    requests["hour_ts"] = pd.to_datetime(requests["hour"], utc=True).dt.tz_localize(None)
    requests["week_file"] = requests["hour_ts"].apply(gdas_week_file)

    weeks = (
        requests.groupby("week_file")["hour_ts"]
        .min().sort_values().index.tolist()
    )
    all_needed = {
        f for ts in requests["hour_ts"] for f in required_week_files(ts)
    }

    print(f"Episodes          : {len(requests):,}")
    print(f"Main GDAS groups  : {len(weeks)}")
    print(f"Unique GDAS files : {len(all_needed)}")

    if results_csv.exists():
        done = pd.read_csv(results_csv)
        done["date"] = pd.to_datetime(done["date"])
        done_keys = set(zip(done["location_id"].astype(str), done["date"]))
        print(f"Resuming          : {len(done_keys):,} already recorded\n")
    else:
        done_keys = set()
        results_csv.write_text(
            "location_id,date,transport_supported,trajectory_km,"
            "mean_height_m,n_points,end_lat,end_lon\n"
        )

    for wi, week in enumerate(weeks, 1):
        subset = requests[requests["week_file"] == week]
        pending = [
            e for e in subset.itertuples(index=False)
            if (str(e.location_id), e.hour_ts) not in done_keys
        ]
        if not pending:
            print(f"[{wi}/{len(weeks)}] {week}: done, skipped")
            continue

        print(f"[{wi}/{len(weeks)}] {week}: {len(pending):,} episodes")

        needed = sorted({
            f for e in pending for f in required_week_files(e.hour_ts)
        })

        try:
            for f in needed:
                download_gdas(f, meteo_dir)
        except Exception as exc:
            print(f"    GDAS download failed: {exc}; group skipped")
            continue

        for n, episode in enumerate(pending, 1):
            tdump_name = f"tdump_{episode.location_id}_{episode.hour_ts:%Y%m%d%H}"
            tdump_path = tdump_dir / tdump_name
            write_control(
                episode,
                required_week_files(episode.hour_ts),
                tdump_name,
                work_dir,
                meteo_dir,
                tdump_dir,
            )

            try:
                subprocess.run(
                    [str(hysplit_exec)],
                    cwd=work_dir,
                    capture_output=True,
                    timeout=120,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                continue

            traj = parse_tdump(tdump_path)
            if traj is None or len(traj) < 2 or traj["age_hours"].min() > -23.5:
                continue

            row = {
                "location_id": episode.location_id,
                "date": episode.hour_ts,
                "transport_supported": "",
                "trajectory_km": round(trajectory_length_km(traj), 1),
                "mean_height_m": round(float(traj["height_m"].mean()), 1),
                "n_points": len(traj),
                "end_lat": round(float(traj["lat"].iloc[-1]), 4),
                "end_lon": round(float(traj["lon"].iloc[-1]), 4),
            }
            pd.DataFrame([row]).to_csv(results_csv, mode="a", header=False, index=False)
            done_keys.add((str(episode.location_id), episode.hour_ts))

            if n % 100 == 0:
                print(f"    {n:,}/{len(pending):,}", flush=True)

        keep_for_next = set()
        if wi < len(weeks):
            next_week = weeks[wi]
            next_subset = requests[requests["week_file"] == next_week]
            keep_for_next = {
                f for ts in next_subset["hour_ts"] for f in required_week_files(ts)
            }

        for f in needed:
            if f not in keep_for_next:
                (meteo_dir / f).unlink(missing_ok=True)

        gc.collect()
        print("    group complete\n")

    print(f"Finished: {results_csv}")


if __name__ == "__main__":
    main()
