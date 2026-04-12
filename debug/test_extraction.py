"""
Full e2e test: Render report for 1 bank, parse data, save to DB, verify.
"""
from src.scraper import OJKScraper
from src.database import Database
import sys

sys.stdout.reconfigure(encoding='utf-8')

db = Database()
db.connect()

# Get bank info
row = db.conn.execute("SELECT nama FROM bank WHERE code = '600083'").fetchone()
bank_name = row[0] if row else ""
print(f"Bank: 600083 - {bank_name}")

s = OJKScraper(db, headless=True)
s.setup_browser()
s.open_page()
s.set_period('Desember', '2024')
s.select_province('DATI01126')
s.select_city('DATI01573')
s.select_bank('600083', bank_name)
s.check_all_reports()

print("\n=== Clicking Tampilkan...")
if not s.click_tampilkan():
    print("FAILED")
    s.driver.quit()
    db.close()
    exit(1)

print("=== Parsing report tables...")
data = s.parse_report_tables()

print(f"\n=== Extraction Results ({len(data)} reports) ===")
for rid, rows in data.items():
    print(f"\n  Report: {rid}")
    print(f"  Rows: {len(rows)}")
    if rows:
        print(f"  Keys: {list(rows[0].keys())}")
        for r in rows[:3]:
            print(f"    {r}")
        if len(rows) > 3:
            print(f"    ... +{len(rows)-3} more")

# Save to DB
print("\n=== Saving to database...")
for rid, rows in data.items():
    if rid == 'BPK-901-000003':
        db.save_kualitas_aset_rows('Desember', '2024', 'DATI01126', 'DATI01573', '600083', rows)
    else:
        db.save_laporan_rows('Desember', '2024', 'DATI01126', 'DATI01573', '600083', rid, rows)
    db.mark_scraped('Desember', '2024', 'DATI01126', 'DATI01573', '600083', rid, 'done')
    print(f"  Saved {rid}: {len(rows)} rows")

# Verify
print("\n=== Database Verification ===")
lap_count = db.conn.execute("SELECT COUNT(*) FROM laporan_data").fetchone()[0]
kap_count = db.conn.execute("SELECT COUNT(*) FROM laporan_kualitas_aset").fetchone()[0]
prog_count = db.conn.execute("SELECT COUNT(*) FROM scrape_progress").fetchone()[0]
print(f"  laporan_data:           {lap_count} rows")
print(f"  laporan_kualitas_aset:  {kap_count} rows")
print(f"  scrape_progress:        {prog_count} entries")

# Show sample rows
print("\n=== Sample laporan_data ===")
for row in db.conn.execute("SELECT jenis_laporan_code, pos, nilai_periode, nilai_tahun_sebelumnya FROM laporan_data LIMIT 5").fetchall():
    print(f"  [{row[0]}] {row[1]}: {row[2]} | {row[3]}")

print("\n=== Sample laporan_kualitas_aset ===")
for row in db.conn.execute("SELECT pos, nilai_l, nilai_dpk, nilai_kl, nilai_d, nilai_m, nilai_jumlah FROM laporan_kualitas_aset LIMIT 5").fetchall():
    print(f"  {row[0]}: L={row[1]} | DPK={row[2]} | KL={row[3]} | D={row[4]} | M={row[5]} | Jumlah={row[6]}")

s.driver.quit()
db.close()
print("\nDONE!")
