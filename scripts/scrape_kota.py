"""
Scrape Kota/Kabupaten dropdown per Provinsi.
Untuk setiap provinsi di database, pilih provinsi → ambil data kota → simpan.
"""
import logging
import time
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
        scraper.open_page()

        # Ambil semua provinsi dari database
        provinces = db.conn.execute(
            "SELECT code, nama FROM provinsi ORDER BY nama"
        ).fetchall()
        logger.info(f"Total provinsi di DB: {len(provinces)}")

        total_kota = 0
        for i, (p_code, p_nama) in enumerate(provinces, 1):
            logger.info(f"[{i}/{len(provinces)}] Provinsi: {p_nama} ({p_code})")

            # Cek apakah sudah punya data kabupaten
            existing = db.conn.execute(
                "SELECT COUNT(*) FROM kabupaten WHERE provinsi_code=?", (p_code,)
            ).fetchone()[0]
            if existing > 0:
                logger.info(f"  → Sudah ada {existing} kota/kab, skip.")
                total_kota += existing
                continue

            try:
                # Pilih provinsi di dropdown
                scraper._select_dropdown_item(config.EXTJS_IDS["province"], p_code)
                time.sleep(2)

                # Tunggu store kota terisi
                scraper._wait_for_store_load(config.EXTJS_IDS["city"], timeout=15)

                # Ambil data kota
                cities = scraper.get_dropdown_options(config.EXTJS_IDS["city"])
                logger.info(f"  → {len(cities)} kota/kabupaten ditemukan")

                for c in cities:
                    db.save_kabupaten(c["value"], c["text"], p_code)

                total_kota += len(cities)

            except Exception as e:
                logger.error(f"  ✗ Error: {e}")
                # Reload page dan coba lanjut
                try:
                    scraper.open_page()
                except:
                    pass

        # Summary
        print("\n" + "=" * 60)
        print("SUMMARY - Kota/Kabupaten per Provinsi")
        print("=" * 60)

        rows = db.conn.execute("""
            SELECT p.nama, COUNT(k.code) as jumlah
            FROM provinsi p
            LEFT JOIN kabupaten k ON k.provinsi_code = p.code
            GROUP BY p.code
            ORDER BY p.nama
        """).fetchall()

        for r in rows:
            print(f"  {r[0]:40s}: {r[1]:>4} kota/kab")

        total = db.conn.execute("SELECT COUNT(*) FROM kabupaten").fetchone()[0]
        print(f"\n  TOTAL KOTA/KABUPATEN: {total}")
        print(f"  Database: {config.DB_PATH}")
        print("=" * 60)

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        scraper.close()
        db.close()


if __name__ == "__main__":
    main()
