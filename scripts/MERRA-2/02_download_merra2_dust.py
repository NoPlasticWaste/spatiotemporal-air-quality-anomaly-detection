"""
Langkah 1 -- Unduh konsentrasi debu permukaan (DUSMASS25) dari MERRA-2.

SUMBER DATA
-----------
NASA MERRA-2, koleksi M2T1NXAER (tavg1_2d_aer_Nx), variabel DUSMASS25 --
konsentrasi massa debu permukaan, fraksi relevan-PM2.5, satuan kg/m3.
Variabel ini SUDAH DIPISAHKAN dari jenis aerosol lain oleh model asimilasi
MERRA-2 sendiri -- tidak perlu langkah tambahan.

STRATEGI RESUME (download terputus)
-------------------------------------
Setiap file ditulis ke path sementara (.nc.tmp) dulu, baru di-rename ke
nama final (.nc) kalau sukses penuh. Artinya:
- File .nc yang ada = LENGKAP, aman dilewati
- File .nc.tmp yang ada = TIDAK LENGKAP, dihapus dan diunduh ulang
Jadi skrip aman dijalankan ulang kapan saja -- melanjutkan tepat dari
titik terakhir tanpa merusak file yang sudah selesai.

STRATEGI MEMORI (tanpa dask, tanpa open_mfdataset)
----------------------------------------------------
open_mfdataset(31 file) memuat metadata semua file sekaligus dan
membutuhkan dask utk lazy loading -- ini yang menyebabkan error sebelumnya.

Skrip ini memproses SATU HARI (satu granul) pada satu waktu:
  - buka satu file
  - potong ke bounding box negara (sel kecil, bukan grid global)
  - simpan array NumPy kecil ke buffer bulan
  - tutup file, bebaskan memori
  - setelah semua hari selesai, tulis satu NetCDF per negara-per-bulan

Peak RAM per iterasi: cuma satu granul harian (~24 jam x ratusan sel),
jauh di bawah satu file global penuh (24 jam x 207.936 sel).

CAKUPAN WILAYAH
---------------
Dipersempit ke bbox wilayah rawan debu berdasar data konsensus sungguhan:
52 dari 143 stasiun ter-flag berada di provinsi rawan-debu (Xinjiang, Tibet,
Inner Mongolia, Gansu, Rajasthan, Gujarat, California, Arizona, Texas).
37 dari 52 belum punya penjelasan kebakaran -- target utama notebook ini.
"""

import gc
import os
import time
from pathlib import Path

import earthaccess
import numpy as np
import pandas as pd
import xarray as xr

# ══════════════════════════════════════════════════════════════════
EXTERNAL_DRIVE = Path("/Volumes/NO NAME")
OUTPUT_DIR = EXTERNAL_DRIVE / "gfed5_era5_data" / "merra2_dust_raw"

NETRC_PATH = Path(
    "/Users/endarlani/Documents/spatiotemporal-air-quality-anomaly-detection/"
    "scripts/MERRA-2/.netrc"
)

START_DATE = "2021-01-01"
END_DATE = "2023-12-31"
SHORT_NAME = "M2T1NXAER"
VARIABLE = "DUSMASS25"

# Bbox wilayah rawan debu + buffer 2 derajat (lat_min, lat_max, lon_min, lon_max)
COUNTRY_BBOX = {
    "China": (27, 52, 82, 122),
    "India": (19, 29, 70, 78),
    "USA":   (27, 43, -123, -100),
}

# Jeda antar granul supaya tidak membebani server NASA -- naikkan kalau
# sering dapat error rate-limit atau koneksi terputus.
DELAY_BETWEEN_GRANULES_SEC = 1
# ══════════════════════════════════════════════════════════════════


def check_prerequisites():
    if not EXTERNAL_DRIVE.exists():
        raise FileNotFoundError(
            f"Drive eksternal tidak ditemukan di {EXTERNAL_DRIVE}. "
            f"Cek nama persisnya: ls /Volumes/"
        )
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    os.environ.setdefault("NETRC", str(NETRC_PATH))
    if not Path(os.environ["NETRC"]).exists():
        raise FileNotFoundError(
            f"File .netrc tidak ditemukan di {os.environ['NETRC']}. "
            f"Ikuti 01_setup_earthdata.md utk membuatnya."
        )

    auth = earthaccess.login(strategy="netrc")
    if not auth.authenticated:
        raise RuntimeError(
            f"Autentikasi NASA Earthdata gagal memakai {os.environ['NETRC']}. "
            f"Periksa isi file .netrc dan pastikan aplikasi "
            f"'NASA GESDISC DATA ARCHIVE' sudah disetujui di akunmu."
        )
    return auth


def cleanup_incomplete_files():
    """Hapus file .tmp dari download sebelumnya yang terputus di tengah jalan."""
    tmp_files = list(OUTPUT_DIR.glob("*.nc.tmp"))
    if tmp_files:
        print(f"Membersihkan {len(tmp_files)} file tidak lengkap dari run sebelumnya:")
        for f in tmp_files:
            f.unlink()
            print(f"  dihapus: {f.name}")
        print()


def lat_lon_names(ds: xr.Dataset) -> tuple[str, str]:
    lat = "lat" if "lat" in ds.coords else "latitude"
    lon = "lon" if "lon" in ds.coords else "longitude"
    return lat, lon


def process_month(period: pd.Period) -> dict[str, bool]:
    """Proses satu bulan -- satu granul harian pada satu waktu.

    Mengembalikan dict {country: sukses/gagal}.
    """
    month_start = period.start_time.strftime("%Y-%m-%d")
    month_end   = period.end_time.strftime("%Y-%m-%d")

    # Tentukan path final dan tmp untuk tiap negara
    final_paths = {
        c: OUTPUT_DIR / f"merra2_dust_{c.lower()}_{period.strftime('%Y%m')}.nc"
        for c in COUNTRY_BBOX
    }
    tmp_paths = {c: Path(str(p) + ".tmp") for c, p in final_paths.items()}

    # Negara yang masih perlu diproses (belum ada file finalnya)
    pending = [c for c in COUNTRY_BBOX if not final_paths[c].exists()]
    if not pending:
        print(f"[{period}] semua negara sudah lengkap, dilewati.")
        return {c: True for c in COUNTRY_BBOX}

    # Cari granul harian untuk bulan ini
    results = earthaccess.search_data(
        short_name=SHORT_NAME,
        temporal=(month_start, month_end),
    )
    if not results:
        print(f"[{period}] PERINGATAN: tidak ada granul ditemukan.")
        return {c: False for c in pending}

    n_days = len(results)
    print(f"[{period}] {n_days} granul (hari), memproses satu per satu ...")

    # Buffer per-negara: list of (times, values) per hari
    buffers: dict[str, list[tuple]] = {c: [] for c in pending}
    grid_info: dict[str, tuple] = {}  # {country: (lat_arr, lon_arr)}

    for day_idx, granule in enumerate(results, 1):
        day_label = granule.get("umm", {}).get(
            "TemporalExtent", {}).get(
            "RangeDateTime", {}).get("BeginningDateTime", f"hari-{day_idx}")[:10]

        try:
            fh = earthaccess.open([granule])
            # chunks=None: muat langsung ke NumPy, tanpa dask, tanpa lazy loading
            ds = xr.open_dataset(fh[0], engine="h5netcdf", chunks=None)

            if VARIABLE not in ds.data_vars:
                print(f"  hari {day_idx}/{n_days}: {VARIABLE} tidak ada, dilewati.")
                ds.close(); continue

            lat_name, lon_name = lat_lon_names(ds)
            lat_arr = ds[lat_name].values
            lon_arr = ds[lon_name].values

            for country in pending:
                lamin, lamax, lomin, lomax = COUNTRY_BBOX[country]

                lat_mask = (lat_arr >= lamin) & (lat_arr <= lamax)
                lon_mask = (lon_arr >= lomin) & (lon_arr <= lomax)

                # .values memuat ke NumPy sekarang -- hanya sel yang dipilih,
                # bukan seluruh grid global
                vals = ds[VARIABLE].values[:, lat_mask, :][:, :, lon_mask]
                times = pd.to_datetime(ds["time"].values)

                buffers[country].append((times, vals))

                if country not in grid_info:
                    grid_info[country] = (lat_arr[lat_mask], lon_arr[lon_mask])

            ds.close()
            del ds, fh

        except Exception as exc:
            print(f"  hari {day_idx}/{n_days} ({day_label}): GAGAL -- {exc}")

        if day_idx % 5 == 0:
            print(f"  {day_idx}/{n_days} hari diproses ...")
            gc.collect()

        time.sleep(DELAY_BETWEEN_GRANULES_SEC)

    # Tulis satu file NetCDF per negara dari buffer yang sudah terkumpul
    results_ok = {}
    for country in pending:
        if not buffers[country]:
            print(f"  [{country}] tidak ada data berhasil diproses, dilewati.")
            results_ok[country] = False
            continue

        try:
            all_times = np.concatenate([t for t, _ in buffers[country]])
            all_vals  = np.concatenate([v for _, v in buffers[country]], axis=0)
            lat_c, lon_c = grid_info[country]

            ds_out = xr.Dataset(
                {VARIABLE: (["time", "lat", "lon"], all_vals.astype("float32"))},
                coords={"time": all_times, "lat": lat_c, "lon": lon_c},
                attrs={"source": "MERRA-2 M2T1NXAER DUSMASS25",
                       "units": "kg m-3",
                       "note": "subset to dust-prone bbox; convert x1e9 for ug/m3"}
            )

            tmp_path = tmp_paths[country]
            ds_out.to_netcdf(tmp_path)
            ds_out.close()

            # Rename .tmp -> .nc hanya kalau tulis sukses penuh
            tmp_path.rename(final_paths[country])
            size_mb = final_paths[country].stat().st_size / 1e6
            print(f"  [{country}] selesai -> {final_paths[country].name} ({size_mb:.1f} MB)")
            results_ok[country] = True

        except Exception as exc:
            print(f"  [{country}] GAGAL menulis file: {exc}")
            if tmp_paths[country].exists():
                tmp_paths[country].unlink()
            results_ok[country] = False

        finally:
            buffers[country].clear()
            gc.collect()

    return results_ok


# ── MAIN ──────────────────────────────────────────────────────────
check_prerequisites()
cleanup_incomplete_files()

months = pd.period_range(START_DATE, END_DATE, freq="M")
print(f"Total {len(months)} bulan x {len(COUNTRY_BBOX)} negara akan diproses.\n")

failed = []
for period in months:
    result = process_month(period)
    month_failed = [c for c, ok in result.items() if not ok]
    if month_failed:
        failed.append((str(period), month_failed))
    print()

print("=" * 56)
if failed:
    print(f"SELESAI dengan {len(failed)} bulan bermasalah:")
    for p, countries in failed:
        print(f"  {p}: {countries}")
    print("Jalankan ulang skrip ini untuk mencoba ulang bulan yang gagal.")
else:
    print("SELESAI. Semua bulan berhasil.")
print(f"\nCATATAN: DUSMASS25 dalam satuan kg/m3.")
print(f"Skrip ekstraksi (03) mengonversi ke ug/m3 (x1e9).")
