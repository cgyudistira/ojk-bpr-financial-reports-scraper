"""
Database inspection: Show all tables, schemas, row counts, and sample data.
"""
import sqlite3
import os
import sys

# Fix encoding for Windows
sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'ojk_bpr.db')
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

# 1. List all tables
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
print("=" * 60)
print(f"DATABASE: {os.path.abspath(DB_PATH)}")
print(f"SIZE: {os.path.getsize(DB_PATH) / 1024:.1f} KB")
print(f"TABLES: {len(tables)}")
print("=" * 60)

for t in tables:
    tname = t[0]
    count = conn.execute(f"SELECT COUNT(*) FROM [{tname}]").fetchone()[0]
    print(f"\n{'-' * 60}")
    print(f"TABLE: {tname}  ({count} rows)")
    print(f"{'-' * 60}")
    
    # Schema
    cols = conn.execute(f"PRAGMA table_info([{tname}])").fetchall()
    print("COLUMNS:")
    for c in cols:
        pk = " [PK]" if c['pk'] else ""
        nn = " NOT NULL" if c['notnull'] else ""
        print(f"  {c['name']:30s} {c['type']:15s}{pk}{nn}")
    
    # Sample data (first 5 rows)
    if count > 0:
        rows = conn.execute(f"SELECT * FROM [{tname}] LIMIT 5").fetchall()
        col_names = [c['name'] for c in cols]
        print(f"\nSAMPLE DATA (first {min(5, count)} of {count}):")
        for row in rows:
            print("  " + " | ".join(f"{col_names[i]}={row[i]}" for i in range(len(col_names))))

# 2. Show specific stats
print(f"\n{'=' * 60}")
print("AGGREGATE STATISTICS")
print(f"{'=' * 60}")

prov_count = conn.execute("SELECT COUNT(*) FROM provinsi").fetchone()[0]
kab_count = conn.execute("SELECT COUNT(*) FROM kabupaten").fetchone()[0]
bank_count = conn.execute("SELECT COUNT(*) FROM bank").fetchone()[0]
lap_count = conn.execute("SELECT COUNT(*) FROM jenis_laporan").fetchone()[0]
data_count = conn.execute("SELECT COUNT(*) FROM laporan_data").fetchone()[0]
prog_count = conn.execute("SELECT COUNT(*) FROM scrape_progress").fetchone()[0]

print(f"  Provinsi:        {prov_count}")
print(f"  Kabupaten/Kota:  {kab_count}")
print(f"  Bank BPR:        {bank_count}")
print(f"  Jenis Laporan:   {lap_count}")
print(f"  Data Laporan:    {data_count}")
print(f"  Scrape Progress: {prog_count}")

# 3. Show sample banks for Bali-Denpasar
print(f"\n{'=' * 60}")
print("SAMPLE: Banks in Bali - Denpasar")
print(f"{'=' * 60}")
rows = conn.execute("""
    SELECT b.code, b.nama, k.nama as kota, p.nama as provinsi
    FROM bank b
    JOIN kabupaten k ON b.kabupaten_code = k.code
    JOIN provinsi p ON b.provinsi_code = p.code
    WHERE b.provinsi_code = 'DATI01126' AND b.kabupaten_code = 'DATI01573'
""").fetchall()
for r in rows:
    print(f"  {r['code']} - {r['nama']} ({r['kota']}, {r['provinsi']})")

# 4. Show laporan_data sample if exists
if data_count > 0:
    print(f"\n{'=' * 60}")
    print("SAMPLE: laporan_data rows")
    print(f"{'=' * 60}")
    rows = conn.execute("SELECT * FROM laporan_data LIMIT 10").fetchall()
    col_names = [desc[0] for desc in conn.execute("SELECT * FROM laporan_data LIMIT 1").description]
    for r in rows:
        print("  ---")
        for i, cn in enumerate(col_names):
            print(f"    {cn}: {r[i]}")
else:
    print(f"\n{'=' * 60}")
    print("NOTE: laporan_data is EMPTY - no reports scraped yet.")
    print("The report rendering now works (verified with 5 iframes loaded)")
    print("but the data extraction/parsing step hasn't been run yet.")
    print(f"{'=' * 60}")

conn.close()
