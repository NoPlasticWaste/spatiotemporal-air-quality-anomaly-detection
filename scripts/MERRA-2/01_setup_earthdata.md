# Langkah 0 — Setup Akun & Kredensial NASA Earthdata (sekali saja)

1. Daftar akun gratis di https://urs.earthdata.nasa.gov/users/new
2. Setelah login, buka **Applications → Authorized Apps**, cari dan setujui aplikasi **"NASA GESDISC DATA ARCHIVE"** — tanpa ini, unduhan akan ditolak meski akun sudah aktif.
3. Buka halaman dataset dan terima lisensinya (kalau ada langkah serupa CDS API sebelumnya untuk ERA5).

## Buat file `.netrc` di dalam folder proyek

Berbeda dari konvensi standar (biasanya di `~/.netrc`), file ini akan disimpan di:

```
/Users/endarlani/Documents/spatiotemporal-air-quality-anomaly-detection/scripts/MERRA-2/.netrc
```

```bash
mkdir -p "/Users/endarlani/Documents/spatiotemporal-air-quality-anomaly-detection/scripts/MERRA-2"
cat > "/Users/endarlani/Documents/spatiotemporal-air-quality-anomaly-detection/scripts/MERRA-2/.netrc" << 'EOF'
machine urs.earthdata.nasa.gov
login USERNAME_KAMU
password PASSWORD_KAMU
EOF
chmod 600 "/Users/endarlani/Documents/spatiotemporal-air-quality-anomaly-detection/scripts/MERRA-2/.netrc"
```

## WAJIB — cegah file ini ter-commit ke git

Karena folder ini bagian dari repo yang aktif di-push ke GitHub, file berisi password polos ini **harus** dikecualikan git. Jalankan ini SEKALI:

```bash
cd /Users/endarlani/Documents/spatiotemporal-air-quality-anomaly-detection
echo "scripts/MERRA-2/.netrc" >> .gitignore
git add .gitignore
git commit -m "Exclude MERRA-2 .netrc credentials from version control"
git push
```

**Verifikasi sebelum lanjut** — pastikan git benar-benar mengabaikannya:

```bash
git status
```

File `.netrc` TIDAK BOLEH muncul di daftar "Untracked files" maupun "Changes to be committed". Kalau masih muncul, JANGAN lanjut ke langkah berikutnya — kabari dulu.

## Arahkan `earthaccess` ke lokasi kustom ini

`earthaccess` secara default mencari `.netrc` di folder home (`~/.netrc`), bukan folder proyek. Supaya ia membaca lokasi kustom ini, environment variable `NETRC` harus diset **sebelum** menjalankan skrip Python manapun yang memanggil `earthaccess.login()`:

```bash
export NETRC="/Users/endarlani/Documents/spatiotemporal-air-quality-anomaly-detection/scripts/MERRA-2/.netrc"
```

Baris `export` ini perlu dijalankan di **setiap sesi terminal baru** sebelum menjalankan skrip unduhan — atau tambahkan ke `~/.zshrc` (atau `~/.bash_profile`) supaya otomatis aktif setiap buka terminal:

```bash
echo 'export NETRC="/Users/endarlani/Documents/spatiotemporal-air-quality-anomaly-detection/scripts/MERRA-2/.netrc"' >> ~/.zshrc
```

## Pasang pustaka yang dibutuhkan

```bash
conda activate crea
pip install earthaccess xarray netCDF4
```

`--break-system-packages` TIDAK diperlukan di conda env — flag itu khusus mengatasi proteksi Python sistem Linux/Debian, bukan kasus di sini.

## Catatan penting

Skrip pada langkah berikutnya BELUM PERNAH saya jalankan sungguhan terhadap server NASA — lingkungan kerja saya tidak punya akses jaringan ke domain nasa.gov. Skrip ditulis berdasar dokumentasi resmi `earthaccess` dan format granul MERRA-2 yang terverifikasi lewat pencarian, tapi kamu adalah orang pertama yang benar-benar menjalankannya.
