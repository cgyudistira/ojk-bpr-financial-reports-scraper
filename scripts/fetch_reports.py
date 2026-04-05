"""
OJK BPR Konvensional Scraper — SQLite Direct HTML Extraction
Main Entry Point
"""
import argparse
import logging
import sys
import os

from src import config
from src.database import Database
from src.scraper import OJKScraper

# Setup logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(config.LOG_FILE, encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="OJK BPR Konvensional Scraper")
    
    parser.add_argument(
        "--mode",
        choices=["metadata", "reports", "all"],
        default="reports",
        help="Scraping mode: 'metadata' to populate Prov/City/Bank, 'reports' to fetch financial data."
    )
    
    parser.add_argument(
        "--bulan",
        default="Desember",
        help="Reporting month (e.g. 'Desember', 'Maret', 'Juni', 'September')"
    )
    
    parser.add_argument(
        "--tahun",
        default="2024",
        help="Reporting year (e.g. '2024')"
    )
    
    parser.add_argument(
        "--provinsi",
        help="Provinsi code to filter (e.g. 'DATI01126' for Bali)"
    )

    parser.add_argument(
        "--kota",
        help="Kota/Kabupaten code to filter (e.g. 'DATI01573' for Denpasar)"
    )

    parser.add_argument(
        "--max-banks",
        type=int,
        help="Limit total banks to process (for testing)"
    )
    
    parser.add_argument(
        "--headless",
        action="store_true",
        default=config.HEADLESS,
        help="Run browser in headless mode"
    )

    args = parser.parse_args()

    # Initialize Database
    db = Database()
    db.connect()

    # Initialize Scraper
    scraper = OJKScraper(db, headless=args.headless)
    
    try:
        scraper.setup_browser()
        
        if args.mode in ["metadata", "all"]:
            logger.info(">>> MODE: Metadata Scraping")
            scraper.scrape_metadata()
            
        if args.mode in ["reports", "all"]:
            logger.info(f">>> MODE: Report Scraping ({args.bulan} {args.tahun})")
            scraper.scrape_reports(
                bulan=args.bulan,
                tahun=args.tahun,
                max_banks=args.max_banks,
                prov_code=args.provinsi,
                city_code=args.kota
            )
            
        logger.info("Scraping workflow completed successfully.")
        
    except KeyboardInterrupt:
        logger.warning("Scraper stopped by user.")
    except Exception as e:
        logger.error(f"Critical error in main: {e}", exc_info=True)
    finally:
        scraper.close()
        db.close()


if __name__ == "__main__":
    main()
