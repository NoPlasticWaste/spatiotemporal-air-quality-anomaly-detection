# HYSPLIT Transport Validation Pipeline

Folder ini berisi pipeline untuk memvalidasi apakah episode anomali
PM2.5 memiliki dukungan fisik dari **transport massa udara jarak jauh**,
menggunakan **HYSPLIT backward trajectories**, meteorologi **GDAS1**,
dan cross-reference emisi kebakaran **GFED5**.

Pipeline ini dibuat untuk episode stasiun--waktu yang tidak beraturan.
Karena itu, file `CONTROL` HYSPLIT ditulis langsung untuk setiap
episode, bukan menggunakan bulk trajectory PySPLIT yang lebih cocok
untuk grid waktu teratur.

## Metodologi dan alur penelitian

Secara konseptual, alurnya adalah:

``` text
Episode anomali PM2.5
        |
        v
hysplit_validation_requests.csv
        |
        v
04_run_hysplit_batch.py
        |
        |  HYSPLIT local
        |  GDAS1 meteorology
        |  24-hour backward trajectory
        |  start height = 100 m AGL
        v
HYSPLIT trajectory results + raw tdump
        |
        +-------------------------------+
        |                               |
        v                               v
04_rerun_failed_hysplit.py       audit trajectory
        |                               |
        +---------------<---------------+
        |
        v
trajectory set yang lengkap
        |
        v
05_determine_transport_supported.py
        |
        |  cross-reference trajectory
        |  dengan GFED5 fire emissions
        v
transport_supported = True / False
        |
        v
hysplit_validation_results_final.csv
        |
        v
filter_hysplit_results.py
        |
        |  cocokkan location_id + timestamp
        |  dengan request penelitian terbaru
        v
data/processed/hysplit_validation_results.csv
        |
        v
Analisis akhir / notebook penelitian
```

### 1. Pemilihan episode

Input utama adalah `hysplit_validation_requests.csv`. Setiap baris
mewakili satu pasangan stasiun dan waktu yang perlu diuji dengan
HYSPLIT.

Informasi utama yang digunakan meliputi:

-   `location_id`
-   `hour`
-   `latitude`
-   `longitude`

### 2. HYSPLIT backward trajectory

Untuk setiap episode, HYSPLIT dijalankan dengan parameter utama:

-   trajectory direction: **backward**
-   duration: **24 jam**
-   starting height: **100 m AGL**
-   meteorological data: **GDAS1**

Karena timestamp episode tidak membentuk grid waktu reguler, script
menulis file `CONTROL` secara langsung.

GDAS diproses secara **streaming**: file meteorologi mingguan diunduh
ketika dibutuhkan, digunakan untuk trajectory terkait, kemudian dapat
dihapus setelah tidak diperlukan lagi. Script juga memperhitungkan
kebutuhan meteorologi lintas boundary file serta buffer interpolasi
`+3 jam`, terutama untuk episode pada pukul 22/23 UTC.

Raw trajectory disimpan sebagai file `tdump`.

### 3. Audit dan rerun trajectory gagal

Trajectory yang gagal atau belum lengkap dapat dikumpulkan ke CSV
request rerun dan diproses kembali dengan `04_rerun_failed_hysplit.py`.

Tujuannya adalah memastikan episode yang akan digunakan pada tahap
validasi transport memiliki trajectory HYSPLIT yang lengkap.

### 4. Cross-reference dengan GFED5

Setelah trajectory tersedia, `05_determine_transport_supported.py`
membandingkan jalur backward trajectory dengan emisi kebakaran GFED5.

Dataset yang digunakan dalam pipeline saat ini:

-   **GFED5.1 stable** untuk 2021--2022
-   **GFED5 NRT** untuk 2023

Hari kebakaran signifikan ditentukan relatif terhadap distribusi emisi
PM2.5 pada grid yang sama dalam bulan tersebut. Implementasi saat ini
menggunakan **persentil ke-90 (P90)** dan mensyaratkan emisi lebih besar
dari nol.

`transport_supported=True` diberikan ketika backward trajectory
melintasi setidaknya satu grid GFED5 yang memenuhi kriteria fire-day
dalam jendela tanggal trajectory.

Interpretasi penting:

> `transport_supported=True` menunjukkan adanya penjelasan fisik yang
> masuk akal berupa transport dari wilayah dengan emisi kebakaran
> signifikan.

Sebaliknya:

> `transport_supported=False` **tidak** berarti episode pasti bukan
> akibat transport dan **tidak** berarti episode pasti manipulasi.

Pipeline GFED5 ini hanya menguji dukungan dari **kebakaran**. Sumber
lain seperti industri, debu, konstruksi, sumber lokal, atau sumber
antropogenik lain belum diuji oleh tahap ini.

### 5. Filtering ke episode penelitian

Master HYSPLIT dapat berisi trajectory dari request yang lebih besar
atau versi dataset sebelumnya.

`filter_hysplit_results.py` mencocokkan:

``` text
location_id + timestamp
```

antara master result dan `hysplit_validation_requests.csv` yang sedang
digunakan oleh penelitian.

Hasil subset inilah yang kemudian disimpan sebagai:

``` text
data/processed/hysplit_validation_results.csv
```

dan digunakan oleh analisis/notebook berikutnya.

------------------------------------------------------------------------

## Deskripsi script

### `04_run_hysplit_batch.py`

Script utama untuk menghasilkan HYSPLIT backward trajectories.

Fungsi utamanya:

-   membaca episode dari request CSV;
-   memetakan timestamp ke file GDAS1 yang diperlukan;
-   mengunduh GDAS1 secara streaming;
-   menulis file `CONTROL`;
-   menjalankan executable HYSPLIT `hyts_std`;
-   membaca output `tdump`;
-   menghitung panjang trajectory;
-   menyimpan ringkasan trajectory;
-   mempertahankan `tdump` untuk tahap GFED5.

Output utama:

``` text
<work-dir>/hysplit_validation_results.csv
<work-dir>/tdump/
```

Kolom `transport_supported` pada tahap ini belum diisi.

### `04_rerun_failed_hysplit.py`

Digunakan untuk menjalankan kembali subset episode yang gagal atau perlu
dihitung ulang.

Script ini memakai logika trajectory yang sama dengan
`04_run_hysplit_batch.py`, tetapi input `--requests-csv` diarahkan ke
CSV yang hanya berisi episode rerun.

Contoh input:

``` text
hysplit_rerun_requests.csv
```

### `05_determine_transport_supported.py`

Menggabungkan hasil trajectory HYSPLIT dengan data kebakaran GFED5.

Fungsi utama:

-   membaca master hasil HYSPLIT;
-   membaca raw `tdump`;
-   membaca GFED5.1 stable dan GFED5 NRT;
-   membangun indeks fire-day;
-   memeriksa apakah trajectory melintasi grid fire-day;
-   mengisi `transport_supported`;
-   menambahkan flag `stagnant` untuk trajectory `<100 km`;
-   menghasilkan final master result.

Output default:

``` text
<work-dir>/hysplit_validation_results_final.csv
```

### `filter_hysplit_results.py`

Menyaring master HYSPLIT final agar hanya berisi episode yang terdapat
pada request penelitian terbaru.

Pencocokan dilakukan berdasarkan:

``` text
location_id + timestamp
```

Script juga melaporkan jumlah request yang tidak ditemukan sehingga
filtering dapat diaudit.

------------------------------------------------------------------------

## Prasyarat

Pipeline memerlukan:

1.  instalasi lokal **HYSPLIT** dan executable `hyts_std`;
2.  Python environment dengan dependency yang diperlukan;
3.  akses internet untuk pengunduhan GDAS1 saat menjalankan trajectory;
4.  file GFED5 lokal untuk tahap cross-reference.

Contoh dependency Python utama:

``` text
numpy
pandas
xarray
netCDF4
```

Aktifkan environment Python yang sesuai sebelum menjalankan script.

------------------------------------------------------------------------

## Cara menjalankan

Semua command berikut diasumsikan dijalankan dari **root repository**:

``` bash
cd /path/to/spatiotemporal-air-quality-anomaly-detection
```

Path data besar sengaja diberikan melalui command-line argument. Dengan
demikian script tidak bergantung pada nama external drive tertentu.

### A. Jalankan HYSPLIT batch

``` bash
python scripts/hysplit/04_run_hysplit_batch.py \
  --hysplit-exec /path/to/hysplit/exec/hyts_std \
  --work-dir /path/to/hysplit-validation \
  --requests-csv data/processed/hysplit_validation_requests.csv
```

Contoh pada komputer pengembang:

``` bash
python scripts/hysplit/04_run_hysplit_batch.py \
  --hysplit-exec ~/hysplit/exec/hyts_std \
  --work-dir "/Volumes/NO NAME/hysplit-validation" \
  --requests-csv data/processed/hysplit_validation_requests.csv
```

### B. Rerun episode gagal

Siapkan CSV yang hanya berisi episode yang perlu dijalankan ulang,
kemudian:

``` bash
python scripts/hysplit/04_rerun_failed_hysplit.py \
  --hysplit-exec /path/to/hysplit/exec/hyts_std \
  --work-dir /path/to/hysplit-validation \
  --requests-csv /path/to/hysplit_rerun_requests.csv
```

### C. Tentukan `transport_supported` dari GFED5

Setelah seluruh trajectory selesai:

``` bash
python scripts/hysplit/05_determine_transport_supported.py \
  --work-dir /path/to/hysplit-validation \
  --gfed-stable-dir /path/to/GFED5/stable_2021_2022 \
  --gfed-nrt-dir /path/to/GFED5NRT
```

Contoh pada komputer pengembang:

``` bash
python scripts/hysplit/05_determine_transport_supported.py \
  --work-dir "/Volumes/NO NAME/hysplit-validation" \
  --gfed-stable-dir "/Volumes/NO NAME/gfed5_data/stable_2021_2022" \
  --gfed-nrt-dir "/Volumes/NO NAME/GFED5NRT"
```

Untuk menentukan lokasi output sendiri:

``` bash
python scripts/hysplit/05_determine_transport_supported.py \
  --work-dir /path/to/hysplit-validation \
  --gfed-stable-dir /path/to/GFED5/stable_2021_2022 \
  --gfed-nrt-dir /path/to/GFED5NRT \
  --output-csv /path/to/hysplit_validation_results_final.csv
```

### D. Filter ke request penelitian terbaru

``` bash
python scripts/hysplit/filter_hysplit_results.py \
  --results /path/to/hysplit-validation/hysplit_validation_results_final.csv \
  --requests data/processed/hysplit_validation_requests.csv \
  --output data/processed/hysplit_validation_results.csv
```

Script akan menampilkan jumlah master results, jumlah request relevan,
jumlah hasil yang cocok, request yang tidak ditemukan, serta proporsi
`transport_supported=True`.

------------------------------------------------------------------------

## Data yang tidak disimpan di Git

Raw dan external datasets berikut **tidak perlu di-commit ke
repository** karena ukurannya besar dan/atau merupakan intermediate
data:

``` text
GDAS1 meteorological files
GFED5.1 NetCDF
GFED5 NRT NetCDF
raw HYSPLIT tdump files
temporary HYSPLIT working files
```

Repository cukup menyimpan:

``` text
scripts/hysplit/
data/processed/hysplit_validation_requests.csv
data/processed/hysplit_validation_results.csv
```

sepanjang ukuran processed CSV masih sesuai untuk Git.

Contoh `.gitignore`:

``` gitignore
# HYSPLIT intermediate / large external data
**/meteo/
**/tdump/
**/CONTROL
*.part

# Large fire-emission datasets
GFED5*/
*.nc
```

Jangan menambahkan aturan `*.csv` secara umum karena processed HYSPLIT
request/result yang kecil justru perlu dapat dilacak oleh Git.

------------------------------------------------------------------------

## Reproducibility

Pipeline memisahkan tiga jenis artefak:

**Code**\
Disimpan di Git dan mendefinisikan cara trajectory serta validasi
transport dihitung.

**Large external/intermediate data**\
GDAS, GFED5, dan raw `tdump` disimpan di luar Git.

**Processed analytical results**\
Subset hasil yang diperlukan untuk analisis penelitian disimpan di
`data/processed/`.

Pemisahan ini menjaga repository tetap ringan sekaligus mempertahankan
metodologi yang dapat direproduksi.
