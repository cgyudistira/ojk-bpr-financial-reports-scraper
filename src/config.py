"""
Configuration constants for OJK BPR Konvensional Scraper v2.
"""
import os

# ============================================================
# URL & Page Settings
# ============================================================
OJK_BASE_URL = (
    "https://cfs.ojk.go.id/cfs/Report.aspx"
    "?BankTypeCode=BPK&BankTypeName=BPR%20Konvensional"
)

# ============================================================
# ExtJS Component IDs
# ============================================================
EXTJS_IDS = {
    "month": "Month",
    "year": "Year",
    "province": "ProvinceCode",
    "city": "CityCode",
    "bank": "BankCode",
    "report_tree": "ReportTree",
}

# ============================================================
# Report Types — ReportTree node IDs → display names
# Discovered from live website ReportTree store
# ============================================================
REPORT_TYPES = {
    "BPK-901-000001": "Laporan Posisi Keuangan",
    "BPK-901-000002": "Laporan Laba Rugi",
    "BPK-901-000003": "Laporan Kualitas Aset Produktif",
    "BPK-901-000004": "Laporan Komitmen dan Kontinjensi",
    "BPK-901-000005": "Laporan Informasi Lainnya",
}

# ============================================================
# Directories & Database
# ============================================================
# BASE_DIR is the root of the project (parent of src/)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "ojk_bpr.db")
DOWNLOAD_DIR = os.path.join(BASE_DIR, "output")

# Ensure directories exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, "logs"), exist_ok=True)

# ============================================================
# Selenium / Browser Settings
# ============================================================
HEADLESS = True
PAGE_LOAD_TIMEOUT = 60
IMPLICIT_WAIT = 10

# ============================================================
# Retry & Timing
# ============================================================
MAX_RETRIES = 3
RETRY_DELAY_BASE = 3
REQUEST_DELAY = 2      # seconds between dropdown actions
REPORT_LOAD_WAIT = 5   # seconds to wait for report render

# ============================================================
# Logging
# ============================================================
LOG_FILE = os.path.join(BASE_DIR, "logs", "scraper.log")
LOG_LEVEL = "INFO"
