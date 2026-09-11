"""
Langkah 1 -- Unduh konsentrasi debu permukaan (DUSMASS25) dari MERRA-2.

SUMBER DATA
-----------
NASA MERRA-2, koleksi M2T1NXAER (tavg1_2d_aer_Nx), variabel DUSMASS25 --
konsentrasi massa debu permukaan, fraksi relevan-PM2.5, satuan kg/m3.
Variabel ini SUDAH DIPISAHKAN dari jenis aerosol lain oleh model asimilasi
MERRA-2 sendiri.

RESUME OTOMATIS DI LEVEL HARI (bukan cuma level file)
---------------------------------------------------------
Setiap kali skrip ini dijalankan, untuk tiap (bulan, negara):
  1. Baca file .nc yang sudah ada (kalau ada), ambil tanggal yang SUDAH
     tersimpan di dalamnya.
  2. Bandingkan dengan tanggal yang SEHARUSNYA ada di bulan itu.
  3. Kalau semua tanggal sudah lengkap -> lewati sepenuhnya (cepat).
  4. Kalau ada tanggal yang hilang (file belum pernah dibuat SAMA SEKALI,
     atau ada satu-dua hari yang gagal di run sebelumnya) -> unduh HANYA
     hari-hari yang hilang itu, gabungkan dengan data yang sudah ada,
     tulis ulang filenya.

Ini menyatukan dua kebutuhan sekaligus: melanjutkan bulan yang belum pernah
diunduh, DAN menambal bulan yang sudah ada tapi kekurangan satu-dua hari
akibat error sementara server (502/503) -- tidak perlu skrip terpisah lagi
untuk kasus kedua.

RETRY DENGAN BACKOFF
---------------------
Tiap granul harian dicoba hingga 3x dengan jeda meningkat (5s/15s/30s)
sebelum benar-benar dianggap gagal untuk RUN INI -- error 502/503 dari CDN
NASA umumnya sementara. Kalaupun sampai 3x tetap gagal, hari itu otomatis
akan dicoba lagi di run BERIKUTNYA berkat mekanisme resume di atas.

STRATEGI MEMORI (tanpa dask, tanpa open_mfdataset)
----------------------------------------------------
Memproses SATU HARI (satu granul) pada satu waktu -- buka, potong ke bbox
negara, simpan array NumPy kecil ke buffer, tutup, bebaskan memori. Peak
RAM per iterasi jauh di bawah memuat satu bulan penuh sekaligus.

CAKUPAN WILAYAH
---------------
Dipersempit ke bbox wilayah rawan debu berdasar data konsensus sungguhan:
52 dari 143 stasiun ter-flag berada di provinsi rawan-debu. 37 dari 52
belum punya penjelasan kebakaran -- target utama notebook ini.
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

COUNTRY_BBOX = {
    "China": (27, 52, 82, 122),
    "India": (19, 29, 70, 78),
    "USA":   (27, 43, -123, -100),
}

MAX_RETRIES = 3
RETRY_BACKOFF_SEC = [5, 15, 30]
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
    """Hapus file .tmp yang tertinggal dari run sebelumnya yang terputus paksa
    (mis. proses dimatikan di tengah jalan) -- .tmp yang tersisa TIDAK PERNAH
    valid, karena rename ke nama final hanya terjadi setelah tulis sukses penuh.
    """
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


def existing_dates_in_file(path: Path) -> set:
    """Tanggal (bukan jam) yang sudah tersimpan di file .nc, kalau ada."""
    if not path.exists():
        return set()
    with xr.open_dataset(path) as ds:
        dates = pd.to_datetime(ds["time"].values).normalize().unique()
    return set(pd.Timestamp(d).strftime("%Y-%m-%d") for d in dates)


def granule_date(granule) -> str:
    """Tanggal (YYYY-MM-DD) dari metadata granul earthaccess."""
    return granule.get("umm", {}).get(
        "TemporalExtent", {}).get(
        "RangeDateTime", {}).get("BeginningDateTime", "")[:10]


def fetch_one_day(granule, country_bbox: dict, pending_countries: list):
    """Unduh & potong satu granul harian ke bbox tiap negara yg diminta.

    Mengembalikan dict {country: (times, vals)} utk negara yg berhasil,
    atau None kalau granul ini gagal total setelah semua percobaan retry.
    """
    for attempt in range(MAX_RETRIES):
        try:
            fh = earthaccess.open([granule])
            ds = xr.open_dataset(fh[0], engine="h5netcdf", chunks=None)

            if VARIABLE not in ds.data_vars:
                ds.close()
                return {}  # variabel tak ada -- bukan error transient, jangan retry

            lat_name, lon_name = lat_lon_names(ds)
            lat_arr = ds[lat_name].values
            lon_arr = ds[lon_name].values
            times = pd.to_datetime(ds["time"].values)

            result = {}
            for country in pending_countries:
                lamin, lamax, lomin, lomax = country_bbox[country]
                lat_mask = (lat_arr >= lamin) & (lat_arr <= lamax)
                lon_mask = (lon_arr >= lomin) & (lon_arr <= lomax)
                vals = ds[VARIABLE].values[:, lat_mask, :][:, :, lon_mask]
                result[country] = (times, vals, lat_arr[lat_mask], lon_arr[lon_mask])

            ds.close()
            del ds, fh
            return result

        except Exception as exc:
            is_last = (attempt == MAX_RETRIES - 1)
            if is_last:
                print(f"    GAGAL setelah {MAX_RETRIES}x percobaan -- {exc}")
                return None
            wait = RETRY_BACKOFF_SEC[attempt]
            print(f"    percobaan {attempt+1}/{MAX_RETRIES} gagal "
                  f"({type(exc).__name__}), tunggu {wait}s ...")
            time.sleep(wait)
    return None


def process_month(period: pd.Period) -> dict:
    """Proses satu bulan: deteksi hari yang hilang PER NEGARA, unduh hanya
    yang hilang, gabungkan dgn data lama (kalau ada), tulis ulang.
    """
    month_start = period.start_time.strftime("%Y-%m-%d")
    month_end   = period.end_time.strftime("%Y-%m-%d")
    all_dates_in_month = set(
        d.strftime("%Y-%m-%d") for d in
        pd.date_range(period.start_time, period.end_time, freq="D")
    )

    final_paths = {
        c: OUTPUT_DIR / f"merra2_dust_{c.lower()}_{period.strftime('%Y%m')}.nc"
        for c in COUNTRY_BBOX
    }

    # Deteksi tanggal yang hilang PER NEGARA -- ini yang membuat resume bekerja
    # baik utk bulan yg belum pernah diunduh (semua tanggal hilang) maupun
    # bulan yg sudah ada tapi kekurangan 1-2 hari (cuma tanggal itu yg hilang).
    missing_by_country = {}
    for country, path in final_paths.items():
        existing = existing_dates_in_file(path)
        missing = all_dates_in_month - existing
        if missing:
            missing_by_country[country] = missing

    if not missing_by_country:
        print(f"[{period}] semua negara lengkap, dilewati.")
        return {c: True for c in COUNTRY_BBOX}

    # Ringkasan sebelum mulai -- supaya jelas apakah ini bulan baru atau tambal
    for country, missing in missing_by_country.items():
        total = len(all_dates_in_month)
        n_missing = len(missing)
        status = "belum pernah diunduh" if n_missing == total else f"kurang {n_missing} hari"
        print(f"  [{country}] {status} ({n_missing}/{total})")

    results = earthaccess.search_data(short_name=SHORT_NAME, temporal=(month_start, month_end))
    if not results:
        print(f"[{period}] PERINGATAN: tidak ada granul ditemukan sama sekali.")
        return {c: False for c in missing_by_country}

    # Filter granul: proses HANYA hari yg benar2 dibutuhkan minimal satu negara
    countries_needing_date = {}  # {date: [country, ...]}
    for country, missing in missing_by_country.items():
        for d in missing:
            countries_needing_date.setdefault(d, []).append(country)

    relevant_granules = [g for g in results if granule_date(g) in countries_needing_date]
    print(f"[{period}] {len(relevant_granules)} granul perlu diunduh "
          f"(dari {len(results)} total granul bulan ini) ...")

    buffers = {c: [] for c in missing_by_country}
    grid_info = {}

    for day_idx, granule in enumerate(relevant_granules, 1):
        day = granule_date(granule)
        needed_countries = countries_needing_date.get(day, [])
        if not needed_countries:
            continue

        fetched = fetch_one_day(granule, COUNTRY_BBOX, needed_countries)
        if fetched is None:
            print(f"  hari {day_idx}/{len(relevant_granules)} ({day}): dilewati, "
                  f"akan dicoba lagi di run berikutnya.")
        elif fetched:
            for country, (times, vals, lat_c, lon_c) in fetched.items():
                buffers[country].append((times, vals))
                if country not in grid_info:
                    grid_info[country] = (lat_c, lon_c)

        if day_idx % 5 == 0:
            print(f"  {day_idx}/{len(relevant_granules)} granul diproses ...")
            gc.collect()
        time.sleep(DELAY_BETWEEN_GRANULES_SEC)

    # Gabungkan data baru dgn data lama (kalau ada), tulis ulang tiap negara
    results_ok = {}
    for country in missing_by_country:
        if not buffers[country]:
            # Tidak ada hari baru berhasil diunduh untuk negara ini di run ini
            still_missing = missing_by_country[country]
            print(f"  [{country}] tidak ada hari baru berhasil, "
                  f"{len(still_missing)} hari masih hilang.")
            results_ok[country] = False
            continue

        try:
            new_times = np.concatenate([t for t, _ in buffers[country]])
            new_vals  = np.concatenate([v for _, v in buffers[country]], axis=0)
            lat_c, lon_c = grid_info[country]

            final_path = final_paths[country]
            if final_path.exists():
                # Gabungkan dgn data lama yg sudah ada (kasus tambal-hari)
                with xr.open_dataset(final_path) as old_ds:
                    all_times = np.concatenate([old_ds["time"].values, new_times])
                    all_vals  = np.concatenate([old_ds[VARIABLE].values, new_vals], axis=0)
            else:
                all_times, all_vals = new_times, new_vals

            order = np.argsort(all_times)
            ds_out = xr.Dataset(
                {VARIABLE: (["time", "lat", "lon"], all_vals[order].astype("float32"))},
                coords={"time": all_times[order], "lat": lat_c, "lon": lon_c},
                attrs={"source": "MERRA-2 M2T1NXAER DUSMASS25", "units": "kg m-3"},
            )

            tmp_path = Path(str(final_path) + ".tmp")
            ds_out.to_netcdf(tmp_path)
            ds_out.close()
            tmp_path.rename(final_path)

            # Cek final: apakah SEMUA tanggal bulan ini sekarang lengkap?
            still_missing_count = len(all_dates_in_month - existing_dates_in_file(final_path))
            size_mb = final_path.stat().st_size / 1e6
            if still_missing_count == 0:
                print(f"  [{country}] LENGKAP -> {final_path.name} ({size_mb:.1f} MB)")
                results_ok[country] = True
            else:
                print(f"  [{country}] SEBAGIAN -> {final_path.name} ({size_mb:.1f} MB), "
                      f"masih kurang {still_missing_count} hari, akan dicoba lagi nanti.")
                results_ok[country] = False

        except Exception as exc:
            print(f"  [{country}] GAGAL menulis file: {exc}")
            tmp_path = Path(str(final_paths[country]) + ".tmp")
            if tmp_path.exists():
                tmp_path.unlink()
            results_ok[country] = False

        finally:
            buffers[country].clear()
            gc.collect()

    return results_ok


# ── MAIN ──────────────────────────────────────────────────────────
check_prerequisites()
cleanup_incomplete_files()

months = pd.period_range(START_DATE, END_DATE, freq="M")
print(f"Total {len(months)} bulan x {len(COUNTRY_BBOX)} negara akan diperiksa.\n")

incomplete = []
for period in months:
    result = process_month(period)
    still_bad = [c for c, ok in result.items() if not ok]
    if still_bad:
        incomplete.append((str(period), still_bad))
    print()

print("=" * 56)
if incomplete:
    print(f"SELESAI. {len(incomplete)} bulan masih punya hari yang kurang:")
    for p, countries in incomplete:
        print(f"  {p}: {countries}")
    print("\nJalankan ulang skrip ini -- hari yang masih kurang akan otomatis")
    print("terdeteksi dan dicoba lagi, tanpa mengunduh ulang hari yang sudah ada.")
else:
    print("SELESAI. Semua bulan, semua negara, lengkap.")
print(f"\nCATATAN: DUSMASS25 dalam satuan kg/m3.")
print(f"Skrip ekstraksi (03) mengonversi ke ug/m3 (x1e9).")
