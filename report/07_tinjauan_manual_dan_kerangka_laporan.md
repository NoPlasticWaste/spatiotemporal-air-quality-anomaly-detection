# Tinjauan Manual & Kerangka Laporan Akhir
## CREA PM2.5 Anomaly Detection Challenge

---

# BAGIAN 1 — TINJAUAN MANUAL

Konsensus (NB6) *menyaring* kandidat; ia tidak *membuktikan* manipulasi. Tahap ini
memeriksa kandidat teratas secara manual sebelum masuk laporan. Prinsip: setiap
klaim harus tahan pertanyaan reviewer *"dari mana kamu tahu?"*

## 1.1 Ringkasan hasil konsensus (dari data nyata)

- **3.151 stasiun** dinilai; 2.289 oleh ketiga metode, 862 oleh dua metode.
- Distribusi vote: **2 stasiun** ditandai 3/3 metode, **28 stasiun** ditandai 2 metode,
  357 ditandai 1 metode, 2.764 tidak ditandai.
- **Korelasi antar-metode sangat rendah** (0,05–0,11): ketiga metode menangkap
  sinyal yang berbeda — memperkuat nilai konsensus, tapi membuat kesepakatan
  penuh (3/3) menjadi bukti yang sangat langka dan sangat kuat.

## 1.2 Protokol tinjauan manual (lakukan untuk tiap kandidat teratas)

Untuk tiap stasiun peringkat atas, periksa lima hal:

1. **Plot deret waktu stasiun vs median tetangga** — apakah penyimpangan konsisten
   sepanjang waktu, atau hanya periode tertentu?
2. **Arah penyimpangan (SL/SH)** — under-report (SL) atau over-report (SH)?
3. **Kecukupan data** — apakah n_obs wajar, atau skor tinggi karena sampel kecil?
4. **Konteks Benford negaranya** — apakah negara ini konform secara global?
   (skor Benford Germany/USA harus ditafsirkan hati-hati — lihat 1.4)
5. **Cross-ref kejadian nyata** — apakah lonjakan cocok dgn kebakaran (GFED4) atau
   peristiwa polusi terdokumentasi?

## 1.3 Hasil tinjauan kandidat teratas

**#1 — Stasiun `3033a` (China) — vote 3/3, consensus_score 0,98**
- Z-score −8,76 → **SL (under-report)**: melapor jauh di bawah tetangga.
- Benford: MAD 0,084, suspicion 5,54 SD → pola digit sangat tidak alami.
- Isolation Forest: ditandai.
- **Penilaian:** bukti kuat & konsisten dari tiga sudut independen. Under-reporting
  disertai pola digit janggal = **kandidat manipulasi terkuat**. Prioritas tinjauan #1.

**#3 — Stasiun `2598a` (China) — vote 2/2, Benford suspicion 8,88 SD (tertinggi)**
- Benford MAD 0,121 — paling ekstrem di seluruh dataset.
- **Peringatan tinjauan:** n_obs hanya 3.252, jauh di bawah stasiun China lain (~8.000).
  MAD tinggi bisa *sebagian* artefak sampel kecil. **Wajib** periksa deret waktunya
  sebelum menyimpulkan manipulasi.

**Catatan pola:** Z-score China didominasi under-report (55 SL vs 29 SH) — konsisten
dengan kekhawatiran under-reporting yang terdokumentasi di literatur kualitas udara.

## 1.4 TEMUAN METODOLOGIS KRITIS (wajib masuk laporan)

**Konformitas Benford berbeda tajam per negara:**

| Negara | MAD | Verdict | Implikasi |
|---|---|---|---|
| India | 0,009 | acceptable | Skor Benford **bisa dipercaya** |
| China | 0,013 | marginal | Skor Benford cukup dapat dipercaya |
| Germany | 0,017 | **nonconform** | Skor Benford **hati-hati** |
| USA | 0,025 | **nonconform** | Skor Benford **sangat hati-hati** |

**Konsekuensi:** untuk Germany & USA, data yang jujur pun secara alami tidak
mengikuti Benford. Maka stasiun Germany/USA yang ditandai Benford **tidak boleh**
dituduh manipulasi berdasarkan Benford saja — persis peringatan Bagian B di NB5.
Untuk kedua negara ini, andalkan Z-score & Isolation Forest sebagai bukti utama.

---

# BAGIAN 2 — KERANGKA LAPORAN AKHIR (Gaya CREA)

Struktur mengikuti pola publikasi CREA: ringkas, berbasis bukti, dengan metodologi
transparan dan keterbatasan yang dinyatakan jujur.

## Judul
*Identifying Systematically Irregular PM2.5 Reporting Stations: A Multi-Method
Consensus Approach Across Four Countries*

## Executive Summary (½ halaman)
- Masalah: kualitas & integritas pelaporan di jaringan monitoring PM2.5 skala besar.
- Pendekatan: tiga metode deteksi independen + konsensus.
- Temuan utama: X stasiun ditandai ≥2 metode; kandidat terkuat under-reporting di China.
- Satu kalimat keterbatasan + satu rekomendasi.

## 1. Pendahuluan
- Kenapa integritas data PM2.5 penting (kesehatan, kebijakan).
- Gap: literatur fokus pada *sensor fault* teknis; kontribusi kita = *pelaporan
  tidak jujur* (dimensi institusional). Sitasi: Chen et al. (2018).

## 2. Data
- OpenAQ, 4 negara (China, Germany, India, USA), ~42 juta baris, 2021–2023.
- Ringkas pipeline pembersihan (NB1) & keputusan filter (NB2): completeness ≥50%,
  koreksi left-truncation, penanganan nilai ekstrem.

## 3. Metodologi
Untuk tiap metode: prinsip singkat + kenapa dipilih + parameter (dengan provenance).

- **3.1 Z-score spasial (leave-one-out)** — deteksi under/over-report vs tetangga.
  Ambang divalidasi dari data (bukan asumsi). Kerangka SL/SH dari Chen et al. (2018).
- **3.2 Isolation Forest** — anomali multivariat per negara. contamination=0,05
  (divalidasi empiris via sensitivitas exceedance P99).
- **3.3 Benford** — deteksi pola digit tak alami. **Konformitas divalidasi dulu**
  (global & per negara) sebelum penilaian per-stasiun.
- **3.4 Konsensus** — normalisasi rank per negara + vote count + skor gabungan.
- **Prinsip lintas-metode:** semua per negara (justifikasi: uji KS menunjukkan
  distribusi antar-negara berbeda signifikan, p<0,05).

## 4. Hasil
- **4.1** Ringkasan per metode (jumlah & arah flag per negara).
- **4.2** Konformitas Benford per negara (tabel 1.4 di atas) — temuan penting sendiri.
- **4.3** Korelasi antar-metode (0,05–0,11) — metode saling independen.
- **4.4** Peringkat konsensus: tabel stasiun teratas + tinjauan manual kandidat #1.
- **4.5** Peta spasial stasiun ditandai (per negara, warna dari colors_map).

## 5. Diskusi
- Interpretasi: under-reporting dominan di China; apa artinya.
- **Keterbatasan (jujur):**
  - Konsensus sekuat metode penyusunnya; blind-spot temporal bersama (Z & IF
    memakai rata-rata, mengabaikan waktu).
  - Benford tak andal untuk Germany/USA (nonconform global).
  - Skor tinggi pada stasiun ber-n kecil bisa artefak.
  - Konsensus menyaring, bukan membuktikan; perlu verifikasi lapangan.

## 6. Kesimpulan & Rekomendasi
- X stasiun prioritas untuk audit lanjutan.
- Rekomendasi: fokuskan verifikasi pada kandidat vote ≥2 di India/China dulu
  (di mana semua metode andal).

## Lampiran
- A: Provenance parameter (`parameter_derivation.json`).
- B: Reproducibility — urutan notebook NB1→NB6, `params.yml`.
- C: Referensi.

## Referensi inti
- Chen et al. (2018). ADF: An Anomaly Detection Framework for Large-scale PM2.5
  Sensing Systems. IEEE IoT Journal 5(2).
- Liu et al. (2008). Isolation Forest. ICDM.
- Nigrini (2012). Benford's Law. Wiley.
- Fu et al. (2014). Benford's law applied to AQI data.
- AIrSense (2023). Sensors 23(2) — majority voting.
