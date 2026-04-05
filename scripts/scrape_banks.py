"""
Scrape data Bank (BPR) dari dropdown BankTree.
Untuk setiap kombinasi Provinsi + Kota/Kabupaten:
  1. Pilih Provinsi
  2. Pilih Kota/Kabupaten
  3. Expand BankCode → Baca BankTree store
  4. Simpan semua bank ke database

Script ini idempotent — skip kombinasi yang sudah punya data bank.
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


def get_bank_list(scraper):
    """Read bank list from BankTree TreePanel inside BankCode DropDownField."""
    # Expand to trigger load
    scraper._js("var cmp = Ext.getCmp('BankCode'); if(cmp) cmp.expand();")
    time.sleep(1)
    
    banks_json = scraper._js("""
        var tree = Ext.getCmp('BankTree');
        if (!tree) return '[]';
        var store = tree.getStore();
        var root = store.getRootNode();
        var banks = [];
        root.cascadeBy(function(node) {
            if (node !== root && node.isLeaf()) {
                banks.push({
                    id: node.get('id'),
                    text: node.get('text')
                });
            }
        });
        return JSON.stringify(banks);
    """)
    
    # Collapse dropdown
    scraper._js("var cmp = Ext.getCmp('BankCode'); if(cmp) cmp.collapse();")
    
    try:
        return __import__('json').loads(banks_json) if banks_json else []
    except:
        return []


def main():
    db = Database()
    db.connect()
    scraper = OJKScraper(db, headless=True)
    scraper.setup_browser()

    try:
        scraper.open_page()

        # Ambil semua kombinasi provinsi-kota dari DB
        combos = db.conn.execute("""
            SELECT k.code as kota_code, k.nama as kota_nama,
                   p.code as prov_code, p.nama as prov_nama
            FROM kabupaten k
            JOIN provinsi p ON k.provinsi_code = p.code
            ORDER BY p.nama, k.nama
        """).fetchall()

        logger.info(f"Total kombinasi provinsi-kota: {len(combos)}")

        total_banks = 0
        skipped = 0
        errors = 0
        last_prov_code = None
        page_reloads = 0

        for i, (k_code, k_nama, p_code, p_nama) in enumerate(combos, 1):
            # Cek apakah sudah punya bank untuk kota ini
            existing = db.conn.execute(
                "SELECT COUNT(*) FROM bank WHERE kabupaten_code=? AND provinsi_code=?",
                (k_code, p_code)
            ).fetchone()[0]
            if existing > 0:
                total_banks += existing
                skipped += 1
                continue

            logger.info(f"[{i}/{len(combos)}] {p_nama} > {k_nama}")

            try:
                # Reload page setiap 50 kota untuk stabilitas
                if page_reloads == 0 or (i - skipped) % 50 == 0:
                    scraper.open_page()
                    scraper.set_period("Desember", "2024")
                    page_reloads += 1

                # Pilih provinsi (hanya jika berubah)
                if p_code != last_prov_code:
                    scraper._select_dropdown_item(config.EXTJS_IDS["province"], p_code)
                    time.sleep(2)
                    scraper._wait_for_store_load(config.EXTJS_IDS["city"], timeout=15)
                    last_prov_code = p_code

                # Pilih kota
                scraper._select_dropdown_item(config.EXTJS_IDS["city"], k_code)
                time.sleep(2)

                # Baca bank list
                banks = get_bank_list(scraper)
                logger.info(f"  → {len(banks)} bank ditemukan")

                # Simpan ke DB
                for b in banks:
                    # Parse bank code from text (format: "600007-PT Bank...")
                    bank_code = b["id"]
                    bank_nama = b["text"]
                    # Remove code prefix from name if present
                    if bank_nama.startswith(bank_code + "-"):
                        bank_nama = bank_nama[len(bank_code)+1:]
                    db.save_bank(bank_code, bank_nama, k_code, p_code)

                total_banks += len(banks)

            except Exception as e:
                logger.error(f"  ✗ Error: {e}")
                errors += 1
                # Reload page on error
                try:
                    scraper.open_page()
                    scraper.set_period("Desember", "2024")
                    last_prov_code = None
                except:
                    pass

        # Summary
        total_db = db.conn.execute("SELECT COUNT(*) FROM bank").fetchone()[0]

        print("\n" + "=" * 60)
        print("SUMMARY - Bank per Provinsi")
        print("=" * 60)

        rows = db.conn.execute("""
            SELECT p.nama, COUNT(b.code) as jumlah
            FROM provinsi p
            LEFT JOIN bank b ON b.provinsi_code = p.code
            GROUP BY p.code
            ORDER BY jumlah DESC
        """).fetchall()

        for r in rows:
            if r[1] > 0:
                print(f"  {r[0]:40s}: {r[1]:>5} bank")

        print(f"\n  TOTAL BANK DI DATABASE: {total_db}")
        print(f"  Kombinasi diproses: {len(combos) - skipped}")
        print(f"  Kombinasi di-skip: {skipped}")
        print(f"  Error: {errors}")
        print(f"  Database: {config.DB_PATH}")
        print("=" * 60)

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        scraper.close()
        db.close()


if __name__ == "__main__":
    main()
