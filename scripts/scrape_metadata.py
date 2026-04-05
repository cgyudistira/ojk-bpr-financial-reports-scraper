"""
Scrape dropdown metadata: Bulan, Tahun (2020-2050), dan Provinsi.
Simpan semua ke SQLite database.
"""
import logging
from src.database import Database
from src.scraper import OJKScraper
from src import config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    db = Database()
    db.connect()
    scraper = OJKScraper(db, headless=True)
    scraper.setup_browser()

    try:
        # Open the OJK page
        scraper.open_page()

        # ─── 1. BULAN (Months) ───────────────────────────────
        logger.info("═══ Scraping Bulan (Month) dropdown ═══")
        months = scraper.get_dropdown_options(config.EXTJS_IDS["month"])
        for m in months:
            db.save_bulan(str(m["value"]), m["text"])
            logger.info(f"  Bulan: {m['value']} → {m['text']}")
        logger.info(f"Total bulan: {len(months)}")

        # ─── 2. TAHUN (Years 2020-2050) ──────────────────────
        logger.info("═══ Saving Tahun 2020-2050 ═══")
        for year in range(2020, 2051):
            db.save_tahun(str(year))
            logger.info(f"  Tahun: {year}")
        logger.info(f"Total tahun: 31 (2020-2050)")

        # ─── 3. PROVINSI ─────────────────────────────────────
        logger.info("═══ Scraping Provinsi dropdown ═══")
        provinces = scraper.get_dropdown_options(config.EXTJS_IDS["province"])
        for p in provinces:
            db.save_provinsi(p["value"], p["text"])
            logger.info(f"  Provinsi: {p['value']} → {p['text']}")
        logger.info(f"Total provinsi: {len(provinces)}")

        # ─── 4. JENIS LAPORAN (dari config) ──────────────────
        logger.info("═══ Saving Jenis Laporan ═══")
        for code, nama in config.REPORT_TYPES.items():
            db.save_jenis_laporan(code, nama)
            logger.info(f"  Laporan: {code} → {nama}")
        logger.info(f"Total jenis laporan: {len(config.REPORT_TYPES)}")

        # ─── Summary ─────────────────────────────────────────
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        
        counts = {}
        for tbl in ["bulan", "tahun", "provinsi", "jenis_laporan"]:
            c = db.conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
            counts[tbl] = c
            print(f"  {tbl:20s}: {c} rows")
        
        # Show bulan data
        print("\n  BULAN:")
        for row in db.conn.execute("SELECT value, nama FROM bulan ORDER BY CAST(value AS INTEGER)"):
            print(f"    {row[0]:>3} = {row[1]}")
        
        # Show provinsi data
        print("\n  PROVINSI:")
        for row in db.conn.execute("SELECT code, nama FROM provinsi ORDER BY nama"):
            print(f"    {row[0]} = {row[1]}")

        print("\n" + "=" * 60)
        print("✓ Semua data dropdown berhasil disimpan ke database!")
        print(f"  Database: {config.DB_PATH}")
        print("=" * 60)

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
    finally:
        scraper.close()
        db.close()


if __name__ == "__main__":
    main()
