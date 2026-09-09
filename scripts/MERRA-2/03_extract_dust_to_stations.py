"""
Langkah 2 -- Ekstrak konsentrasi debu per stasiun dari grid MERRA-2.

Skrip 02 kini menulis SATU FILE PER (negara, bulan) -- bukan satu file global
per bulan -- karena tiap file sudah dipotong ke bounding box negaranya
masing-masing sebelum diunduh. Akibatnya grid tiap file BERBEDA cakupan
antar negara (meski resolusinya sama), sehingga stasiun harus dicocokkan
terhadap grid NEGARANYA SENDIRI -- pola yang sama persis dengan skrip
ekstraksi ERA5 (03_extract_and_convert.py), bukan grid tunggal untuk semua
stasiun seperti desain awal skrip ini.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

# ══════════════════════════════════════════════════════════════════
EXTERNAL_DRIVE = Path("/Volumes/NO NAME")
MERRA2_DIR = EXTERNAL_DRIVE / "gfed5_era5_data" / "merra2_dust_raw"
OUTPUT_PATH = Path("../data/processed/dust_hourly.csv")
STATIONS_PATH = Path("../data/processed/NB01_station_locations.csv")
VARIABLE = "DUSMASS25"
KG_TO_UG = 1e9   # kg/m3 -> ug/m3
COUNTRIES = ["China", "Germany", "India", "USA"]
# ══════════════════════════════════════════════════════════════════

if not EXTERNAL_DRIVE.exists():
    raise FileNotFoundError(
        f"Drive eksternal tidak ditemukan di {EXTERNAL_DRIVE}. "
        f"Cek nama persisnya lewat terminal: ls /Volumes/"
    )

stations = pd.read_csv(STATIONS_PATH)[["location_id", "country", "latitude", "longitude"]]
print(f"Stasiun dimuat: {len(stations):,}")


def nearest_index(value: float, grid: np.ndarray) -> int:
    return int(np.abs(grid - value).argmin())


all_rows = []

for country in COUNTRIES:
    country_stations = stations[stations["country"] == country]
    if country_stations.empty:
        continue

    country_files = sorted(MERRA2_DIR.glob(f"merra2_dust_{country.lower()}_*.nc"))
    if not country_files:
        print(f"[{country}] PERINGATAN: tidak ada file ditemukan, dilewati sepenuhnya.")
        continue

    print(f"[{country}] {len(country_stations):,} stasiun, {len(country_files)} file bulanan")

    # Grid diambil dari file PERTAMA negara ini -- semua bulan negara yang sama
    # berbagi grid yang identik (cuma waktu yang berbeda antar file).
    with xr.open_dataset(country_files[0]) as ds0:
        lat_name = "lat" if "lat" in ds0.coords else "latitude"
        lon_name = "lon" if "lon" in ds0.coords else "longitude"
        reference_lat = ds0[lat_name].values.copy()
        reference_lon = ds0[lon_name].values.copy()

    country_stations = country_stations.copy()
    country_stations["lat_idx"] = country_stations["latitude"].apply(
        lambda v: nearest_index(v, reference_lat))
    country_stations["lon_idx"] = country_stations["longitude"].apply(
        lambda v: nearest_index(v, reference_lon))

    lat_take = country_stations["lat_idx"].to_numpy()
    lon_take = country_stations["lon_idx"].to_numpy()
    location_ids = country_stations["location_id"].to_numpy()

    country_parts = []
    for path in country_files:
        with xr.open_dataset(path) as ds:
            if VARIABLE not in ds.data_vars:
                print(f"  PERINGATAN: {VARIABLE} tidak ada di {path.name}, dilewati.")
                continue
            time_dim = "time" if "time" in ds.dims else list(ds.dims)[0]
            values = ds[VARIABLE].values * KG_TO_UG    # (time, lat, lon) -> ug/m3
            times = pd.to_datetime(ds[time_dim].values)
            # Ambil nilai per stasiun langsung dari indeks lat/lon-nya masing2
            # (bukan dari sel yang "ditempati" seperti gfed5/era5 -- di sini
            # jumlah stasiun per negara relatif kecil, jadi pengulangan indeks
            # yang sama utk beberapa stasiun tidak menjadi beban berarti).
            station_values = values[:, lat_take, lon_take]   # (time, n_stations)
        country_parts.append(pd.DataFrame(
            station_values, index=times, columns=location_ids
        ))
        print(f"  {path.name} diproses")

    if not country_parts:
        continue

    country_series = pd.concat(country_parts).sort_index()
    country_long = (country_series.reset_index(names="hour")
                    .melt(id_vars="hour", var_name="location_id", value_name="dust_ug_m3"))
    country_long["country"] = country
    all_rows.append(country_long)

if not all_rows:
    raise RuntimeError("Tidak ada data yang berhasil diekstrak; periksa isi folder MERRA-2.")

dust_hourly = pd.concat(all_rows, ignore_index=True).sort_values(["location_id", "hour"])

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
dust_hourly[["location_id", "country", "hour", "dust_ug_m3"]].to_csv(OUTPUT_PATH, index=False)

print(f"\nSelesai. {len(dust_hourly):,} baris ditulis ke {OUTPUT_PATH}")
print(f"Stasiun tercakup: {dust_hourly['location_id'].nunique():,}")
print(f"Rentang dust_ug_m3: {dust_hourly['dust_ug_m3'].min():.3f} - "
      f"{dust_hourly['dust_ug_m3'].max():.3f}")
