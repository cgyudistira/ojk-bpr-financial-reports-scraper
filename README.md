# OJK BPR Konvensional Web Scraper

Scraper otomatis data publikasi keuangan **BPR Konvensional** dari website Resmi Otoritas Jasa Keuangan (OJK). Proyek ini mengambil 5 tipe laporan keuangan (Negara, Laba Rugi, Kualitas Aset, dsb.) secara modular berdasarkan kombinasi Provinsi, Kabupaten, dan Bank.

## 📁 Struktur Proyek Pendekatan Moderen

Proyek ini telah direstrukturisasi agar standar, modular, dan bersih:

```text
ojk-bpr-financial-reports-scraper/
├── src/                    # Folder Inti: Core logic scraper
│   ├── scraper.py          # Class utama OJKScraper dengan Selenium 
│   ├── database.py         # Pengelolaan koneksi dan data ke SQLite DB
│   ├── config.py           # Konfigurasi konstanta, path, & selector JS
│   └── excel_parser.py     # Parser tabel ekstraksi laporan dari DOM
│
├── scripts/                # Folder Automasi: Skrip operasional
│   ├── fetch_reports.py    # Skrip iterasi pengekstrak data laporan akhir
│   ├── scrape_metadata.py  # Skrip penyokong metadata Provinsi, Kota
│   ├── scrape_kota.py      # Pengambilan Kabupaten spesifik
│   ├── scrape_banks.py     # Pengambilan Entitas Bank spesifik
│   └── check_db.py         # Validasi dan print statistik database internal
│
├── main.py                 # File entry-point di root untuk memantik operasi
├── data/                   # Data master SQLite db (`ojk_bpr.db`) 
├── logs/                   # Log output aplikasi scraper
├── debug/                  # Kumpulan eksperimen bypass ExtJS (Hanya untuk Referensi)
├── tests/                  # Script uji e2e
├── requirements.txt        # Python Dependencies
└── .agents/workflows/      # Dokumentasi Alur Penanganan ExtJS OJK
```

## ⚙️ Persiapan & Instalasi

Pastikan memiliki **Python 3.9+** dan browser **Google Chrome**.

```bash
# Buat Virtual Environment
python -m venv .venv

# Aktifkan Environment (Windows)
.venv\Scripts\activate

# Instal dependensi
pip install -r requirements.txt
```

## 🚀 Panduan Penggunaan

**Jalankan langsung melalui entry-point dari Root Directory:**

```bash
# Scrape seluruh bank (Default: Desember 2024)
python main.py --bulan Desember --tahun 2024

# Uji coba untuk 1 Bank spesifik (Filter Provinsi & Kota) & Batasi kuota Bank (Contoh Bali, Denpasar)
python main.py --bulan Desember --tahun 2024 --provinsi DATI01126 --kota DATI01573 --max-banks 1

# Mode interaktif / non-headless (menampilkan UI Browser Chrome terbuka)
python main.py --bulan Desember --tahun 2024 --max-banks 1 --headless
```

## 🗄️ Struktur Database SQLite (`data/ojk_bpr.db`)

Semua hasil *scraping* dismpan otomatis untuk mencegah pengulangan saat terjadi interupsi:

| Tabel | Inti Data |
|-------|-----------|
| `provinsi` | Kode & Name region dasar |
| `kabupaten`| Kode & Name entitas region per provinsi |
| `bank` | Nama BPR teregulasi, terhubung ke Kode Kabupaten |
| `jenis_laporan` | Meta 5 tipe Laporan OJK |
| `scrape_progress` | Track record ID apa saja yang SUDAH selesai |
| `laporan_data` | **Data Row Keuangan final** |

## 💡 Pengetahuan Bypass UI OJK BPR (ExtJS/Ext.NET)
Aplikasi Web OJK menggunakan renderan ExtJS Ext.NET versi tua yang memblokir *Native DOM Interaction*. Solusi *Bypass* dapat dipelajari mandiri di `/.agents/workflows/ojk_scraper_workflow.md` atau skrip eksperimental di berkas `/debug/`.
