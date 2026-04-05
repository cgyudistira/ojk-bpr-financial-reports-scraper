"""End-to-end test: full scrape flow for 1 bank."""
import logging, time, json
from src.scraper import OJKScraper
from src.database import Database
from src import config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

db = Database()
s = OJKScraper(db, headless=True)
s.setup_browser()

try:
    # Step 1: Open page
    logger.info("=== STEP 1: Open page ===")
    s.open_page()
    
    # Step 2: Set period
    logger.info("=== STEP 2: Set period ===")
    s.set_period("Desember", "2024")
    
    # Step 3: Select province (Jawa Barat)
    logger.info("=== STEP 3: Select province ===")
    s.select_province("DATI00101")
    
    # Step 4: Select city (Kab. Bekasi)
    logger.info("=== STEP 4: Select city ===")
    s.select_city("DATI00102")
    
    # Step 5: Select bank
    logger.info("=== STEP 5: Select bank ===")
    s.select_bank("600007")
    
    # Step 6: Check all reports
    logger.info("=== STEP 6: Check all reports ===")
    s.check_all_reports()
    
    s.driver.save_screenshot(config.DOWNLOAD_DIR + "/debug_e2e_checked.png")
    logger.info("Screenshot: debug_e2e_checked.png")
    
    # Step 7: Click Tampilkan  
    logger.info("=== STEP 7: Click Tampilkan ===")
    result = s.click_tampilkan()
    logger.info(f"Tampilkan result: {result}")
    
    s.driver.save_screenshot(config.DOWNLOAD_DIR + "/debug_e2e_after_tampilkan.png")
    
    # Step 8: Parse tables
    if result:
        logger.info("=== STEP 8: Parse tables ===")
        data = s.parse_report_tables()
        logger.info(f"Parsed {len(data)} report types")
        for rid, rows in data.items():
            name = config.REPORT_TYPES.get(rid, rid)
            logger.info(f"  {name}: {len(rows)} rows")
            for row in rows[:3]:
                logger.info(f"    {row}")
    else:
        logger.warning("Tampilkan failed — no report rendered")
        # Check what's in ReportViewerArea
        area_info = s._js("""
            var area = document.getElementById('ReportViewerArea');
            if (!area) return 'no_area';
            return 'len=' + area.innerHTML.length + ' text=' + area.innerText.trim().substring(0, 200);
        """)
        logger.info(f"ReportViewerArea: {area_info}")

except Exception as e:
    logger.error(f"Error: {e}", exc_info=True)
    s.driver.save_screenshot(config.DOWNLOAD_DIR + "/debug_e2e_error.png")
finally:
    s.close()
    db.close()
