"""
Core Selenium-based scraper for OJK BPR Konvensional publications v4.

Key insight: Uses cmp.expand() + picker.getNode(record).click() for dropdown
selections. This triggers the real Ext.NET DirectEvent postbacks on the server.
Plain fireEvent('select') or setValue() do NOT trigger server-side handlers.
"""
import logging
import os
import re
import time
from functools import wraps
from typing import Optional, List, Dict

from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    StaleElementReferenceException,
    WebDriverException,
    NoSuchElementException,
    JavascriptException,
)
from webdriver_manager.chrome import ChromeDriverManager

from src import config
from src.database import Database

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────
# Retry Decorator
# ────────────────────────────────────────────────────────────
def retry(max_retries: int = config.MAX_RETRIES, delay_base: int = config.RETRY_DELAY_BASE):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except (TimeoutException, StaleElementReferenceException,
                        WebDriverException, JavascriptException) as e:
                    last_exception = e
                    wait_time = delay_base * (2 ** (attempt - 1))
                    logger.warning(
                        f"[Retry {attempt}/{max_retries}] {func.__name__}: {e}. "
                        f"Retrying in {wait_time}s..."
                    )
                    time.sleep(wait_time)
            logger.error(f"{func.__name__} failed after {max_retries} retries.")
            raise last_exception
        return wrapper
    return decorator


# ────────────────────────────────────────────────────────────
# OJK Scraper
# ────────────────────────────────────────────────────────────
class OJKScraper:

    def __init__(self, db: Database, headless: bool = config.HEADLESS):
        self.driver: Optional[webdriver.Chrome] = None
        self.db = db
        self.headless = headless

    # ── Browser Setup ───────────────────────────────────────
    def setup_browser(self):
        logger.info("Setting up Chrome browser...")
        opts = Options()
        if self.headless:
            opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--window-size=1920,1080")
        opts.add_argument("--disable-extensions")
        opts.add_argument("--ignore-certificate-errors")
        
        prefs = {
            "download.default_directory": config.DOWNLOAD_DIR,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        }
        opts.add_experimental_option("prefs", prefs)

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=opts)
        self.driver.set_page_load_timeout(config.PAGE_LOAD_TIMEOUT)
        self.driver.implicitly_wait(config.IMPLICIT_WAIT)
        logger.info("Chrome browser ready.")

    def close(self):
        if self.driver:
            self.driver.quit()
            logger.info("Browser closed.")

    # ── JavaScript helpers ──────────────────────────────────
    def _js(self, script: str, *args):
        return self.driver.execute_script(script, *args)

    @retry()
    def open_page(self):
        logger.info(f"Opening OJK page: {config.OJK_BASE_URL}")
        self.driver.get(config.OJK_BASE_URL)
        WebDriverWait(self.driver, 45).until(
            lambda d: d.execute_script(
                "return typeof Ext !== 'undefined' && Ext.isReady === true"
            )
        )
        time.sleep(3)
        logger.info("Page loaded, ExtJS ready.")

    # ── Dropdown Interactions ───────────────────────────────
    # CRITICAL: We must use expand() + picker.getNode(record).click()
    # This is the ONLY way to trigger Ext.NET DirectEvent postbacks.
    
    def get_dropdown_options(self, component_id: str) -> List[Dict]:
        """Get options from an ExtJS combo box store (read-only, no events)."""
        script = f"""
        var cmp = Ext.getCmp('{component_id}');
        if (!cmp) return [];
        if (typeof cmp.getStore !== 'function') return [];
        var store = cmp.getStore();
        if (!store) return [];
        var items = [];
        store.each(function(record) {{
            items.push({{
                value: record.get(cmp.valueField || 'value'),
                text: record.get(cmp.displayField || 'text')
            }});
        }});
        return items;
        """
        return self._js(script) or []

    @retry()
    def _select_dropdown_item(self, component_id: str, value: str):
        """Select a dropdown item using expand() + picker node click.
        
        This triggers the real Ext.NET DirectEvent postback.
        """
        result = self._js(f"""
        try {{
            var cmp = Ext.getCmp('{component_id}');
            if (!cmp) return 'no_cmp';
            
            var store = cmp.getStore();
            if (!store) return 'no_store';
            
            // Find the record
            var record = store.findRecord(cmp.valueField || 'value', '{value}');
            if (!record) return 'no_record:count=' + store.getCount();
            
            // Expand the dropdown to create the picker
            cmp.expand();
            
            // Wait a tick for the picker to render
            var picker = cmp.getPicker();
            if (!picker) return 'no_picker';
            
            // Find the DOM node for this record and click it
            var node = picker.getNode(record);
            if (node) {{
                node.click();
                return 'ok:' + record.get(cmp.displayField || 'text');
            }}
            
            // Fallback: select programmatically 
            cmp.select(record);
            cmp.fireEvent('select', cmp, [record]);
            return 'fallback:' + record.get(cmp.displayField || 'text');
        }} catch(e) {{
            return 'err:' + e.message;
        }}
        """)
        
        logger.info(f"Dropdown {component_id} = {value} → {result}")
        
        if result and result.startswith('no_record'):
            raise WebDriverException(f"Record not found for {component_id}={value} ({result})")
        if result and result.startswith('err:'):
            raise WebDriverException(f"JS error for {component_id}: {result}")
        
        time.sleep(config.REQUEST_DELAY)

    def _wait_for_store_load(self, component_id: str, timeout: int = 20):
        """Wait until an ExtJS store finishes loading."""
        try:
            WebDriverWait(self.driver, timeout).until(
                lambda d: d.execute_script(f"""
                    var cmp = Ext.getCmp('{component_id}');
                    if (!cmp) return true;
                    if (typeof cmp.getStore !== 'function') return true;
                    var store = cmp.getStore();
                    if (!store) return true;
                    return !store.isLoading() && store.getCount() > 0;
                """) is True
            )
        except TimeoutException:
            logger.warning(f"Store {component_id} still loading/empty after {timeout}s")
        time.sleep(1)

    @retry()
    def set_period(self, bulan: str, tahun: str):
        """Set reporting period. Month/year don't need server postback."""
        month_map = {
            "Januari": 1, "Februari": 2, "Maret": 3, "April": 4, "Mei": 5, "Juni": 6,
            "Juli": 7, "Agustus": 8, "September": 9, "Oktober": 10, "November": 11, "Desember": 12
        }
        month_val = month_map.get(bulan, 1)
        logger.info(f"Setting period: {bulan} ({month_val}) {tahun}")
        
        mid = config.EXTJS_IDS["month"]
        yid = config.EXTJS_IDS["year"]
        
        self._js(f"""
        var m = Ext.getCmp('{mid}');
        if (m) {{ m.setValue({month_val}); }}
        var y = Ext.getCmp('{yid}');
        if (y) {{ y.setValue({tahun}); }}
        """)
        time.sleep(2)

    # ── Cascading Dropdown Selection ─────────────────────────
    def select_province(self, code: str):
        self._select_dropdown_item(config.EXTJS_IDS["province"], code)
        self._wait_for_store_load(config.EXTJS_IDS["city"])

    def select_city(self, code: str):
        self._select_dropdown_item(config.EXTJS_IDS["city"], code)
        time.sleep(config.REQUEST_DELAY)

    @retry()
    def select_bank(self, code: str, bank_name: str = ""):
        """Select bank — BankCode is Ext.net.DropDownField, not a combo.
        It needs setValue() directly, no picker/store involved.
        
        The server expects BankCode in 'code-name' format (e.g. '600083-PT BPR XYZ')
        because ShowReportButton_DirectClick does String.Substring at the hyphen position.
        """
        # Build the full value string the server expects
        if bank_name:
            full_value = f"{code}-{bank_name}"
        else:
            full_value = code
        
        logger.info(f"Selecting bank: {full_value}")
        self._js(f"""
            var cmp = Ext.getCmp('BankCode');
            if (cmp) {{ cmp.setValue('{full_value}'); }}
        """)
        time.sleep(3)
        
        node_count = self._js("""
            var t = Ext.getCmp('ReportTree');
            if (!t) return -1;
            var root = t.getStore().getRootNode();
            return root ? root.childNodes.length : 0;
        """)
        logger.info(f"ReportTree nodes after bank selection: {node_count}")
        if node_count == 0:
            raise WebDriverException("ReportTree empty after bank selection")


    def check_all_reports(self):
        """Check exactly 5 unique report types (handle duplicates)."""
        logger.info("Checking all report types...")
        
        count = self._js("""
        var t = Ext.getCmp('ReportTree');
        if (!t) return 0;
        var seen = {};
        var checked = 0;
        t.getRootNode().cascadeBy(function(node) {
            if (node.isLeaf()) {
                var text = node.get('text');
                if (!seen[text]) {
                    // Use native ExtJS onCheckChange - this correctly serializes
                    // the node into Ext.Net.SubmittedNode JSON format in the
                    // hidden 'ReportTree_CheckNodes' field that the ASP.NET
                    // server deserializes. Using fireEvent or join(',') causes
                    // "Could not cast System.String to Ext.Net.SubmittedNode".
                    t.getView().onCheckChange(node, true);
                    seen[text] = true;
                    checked++;
                } else {
                    node.set('checked', false);
                }
            }
        });
        return checked;
        """)
        logger.info(f"Checked {count} unique report types")
        time.sleep(2)

    # ── Report Display (Display) ───────────────────────────
    @retry()
    def click_tampilkan(self):
        """Click Display using getEl().dom.click() for real DOM event."""
        logger.info("Clicking 'Display' button...")
        
        result = self._js("""
        try {
            // FIX: Ext.NET ComboBox submits display text instead of value codes
            // because hiddenName is not configured. The server expects DATI codes
            // in ProvinceCode/CityCode fields (it does Substring on them).
            var prov = Ext.getCmp('ProvinceCode');
            if (prov) { prov.inputEl.dom.value = prov.getValue(); }
            var city = Ext.getCmp('CityCode');
            if (city) { city.inputEl.dom.value = city.getValue(); }
            
            var btn = Ext.getCmp('ShowReportButton');
            if (!btn) return 'no_cmp';
            if (btn.isDisabled()) return 'disabled';
            
            // Use getEl().dom.click() which dispatches a real DOM MouseEvent
            // This triggers the Ext.NET DirectEvent handler on the server
            btn.getEl().dom.click();
            return 'ok';
        } catch(e) {
            return 'err:' + e.message;
        }
        """)
        
        if result != 'ok':
            logger.warning(f"Display click: {result}")
            return False

        logger.info("Waiting for report to render (max 90s)...")
        for i in range(18):
            time.sleep(5)
            info = self._js("""
            var area = document.getElementById('ReportViewerArea');
            if (!area) return { len: 0, has_table: false, text: "", iframes: 0 };
            
            var iframes = area.getElementsByTagName('iframe');
            var total_len = 0;
            var has_table = false;
            var first_text = "";
            
            for (var i=0; i<iframes.length; i++) {
                try {
                    var doc = iframes[i].contentDocument || iframes[i].contentWindow.document;
                    var html = doc.body ? doc.body.innerHTML : "";
                    total_len += html.length;
                    if (html.indexOf('<table') >= 0) has_table = true;
                    if (first_text === "" && doc.body) first_text = doc.body.innerText.trim();
                } catch(e) {}
            }
            
            if (iframes.length === 0) {
                total_len = area.innerHTML.length;
                has_table = area.innerHTML.indexOf('<table') >= 0;
                first_text = area.innerText.trim();
            }
            
            return { len: total_len, has_table: has_table, text: first_text, iframes: iframes.length };
            """)
            
            logger.info(
                f"  +{(i+1)*5}s: len={info['len']}, tables={info['has_table']}, "
                f"iframes={info['iframes']}, text='{str(info.get('text',''))[:80]}'"
            )
            
            if info['has_table'] or info['len'] > 500:
                return True
            if info.get('text'):
                txt = info['text'].lower()
                if 'tidak tersedia' in txt or 'error' in txt:
                    logger.warning(f"Report status: {info['text']}")
                    return True
        
        # Save debug screenshot on timeout
        self.driver.save_screenshot("debug_report_timeout.png")
        logger.warning("Report did not render within 90s")
        return False

    # ── Data Extraction ──────────────────────────────────────
    def parse_report_tables(self) -> Dict[str, List[Dict]]:
        """Extract report data from SSRS iframes in ReportViewerArea.
        
        Uses JavaScript to parse the SSRS report tables directly in the browser,
        which is more reliable than HTML parsing due to deeply nested SSRS layout.
        
        Returns dict mapping report_id -> list of row dicts.
        Laporan 1,2,4: {'pos': str, 'nilai_periode': str, 'nilai_tahun_sebelumnya': str}
        Laporan 3:     {'pos': str, 'nilai_l': str, 'nilai_dpk': str, 'nilai_kl': str,
                         'nilai_d': str, 'nilai_m': str, 'nilai_jumlah': str}
        """
        # Wait for iframe content to fully load (multi-page reports need extra time)
        time.sleep(10)
        
        iframe_count = self._js("""
            var area = document.getElementById('ReportViewerArea');
            return area ? area.getElementsByTagName('iframe').length : 0;
        """)
        
        if not iframe_count:
            logger.warning("No iframes found in ReportViewerArea")
            return {}
        
        results = {}
        
        # Report IDs in order of iframe rendering
        report_ids = list(config.REPORT_TYPES.keys())
        
        for idx in range(min(iframe_count, 5)):
            report_id = report_ids[idx] if idx < len(report_ids) else None
            if not report_id:
                continue
            
            # Skip Laporan 5 (Informasi Lainnya) - non-tabular data
            if report_id == 'BPK-901-000005':
                logger.info(f"  Skipping {config.REPORT_TYPES[report_id]} (non-tabular)")
                continue
            
            # Use different extraction JS for Kualitas Aset (6 value cols)
            if report_id == 'BPK-901-000003':
                rows = self._extract_kualitas_aset(idx)
            else:
                rows = self._extract_standard_report(idx)
            
            if rows:
                results[report_id] = rows
                logger.info(f"  Iframe {idx} ({config.REPORT_TYPES[report_id]}): {len(rows)} rows")
            else:
                logger.warning(f"  Iframe {idx} ({config.REPORT_TYPES[report_id]}): no data")
        
        return results

    def _extract_standard_report(self, iframe_idx: int) -> List[Dict]:
        """Extract 3-column report data (Pos, Periode, Tahun Sebelumnya) from iframe.
        
        Strategy: Find the oReportDiv, then locate the largest table inside it.
        SSRS puts headers and data in separate nested tables. The data table
        is the one with the most rows.
        """
        data = self._js(f"""
            var area = document.getElementById('ReportViewerArea');
            var iframes = area.getElementsByTagName('iframe');
            if ({iframe_idx} >= iframes.length) return [];
            
            var doc = iframes[{iframe_idx}].contentDocument || iframes[{iframe_idx}].contentWindow.document;
            
            // Find the report content div
            var reportDiv = doc.querySelector('[id*="oReportDiv"]');
            if (!reportDiv) return [];
            
            // Find the largest table (by row count) inside report div - that's the data
            var allTables = reportDiv.getElementsByTagName('table');
            var dataTable = null;
            var maxRows = 0;
            
            for (var t = 0; t < allTables.length; t++) {{
                if (allTables[t].rows.length > maxRows) {{
                    maxRows = allTables[t].rows.length;
                    dataTable = allTables[t];
                }}
            }}
            
            if (!dataTable || maxRows < 5) return [];
            
            var results = [];
            var trs = dataTable.rows;
            
            for (var r = 0; r < trs.length; r++) {{
                var cells = trs[r].cells;
                if (!cells || cells.length < 3) continue;
                
                var cellTexts = [];
                for (var c = 0; c < cells.length; c++) {{
                    var txt = cells[c].innerText || '';
                    cellTexts.push(txt.trim().split(String.fromCharCode(10)).join(' '));
                }}
                
                // Skip header/empty rows
                var pos = '';
                var val1 = '';
                var val2 = '';
                
                // Find the cell with meaningful text (pos name)
                // Skip leading empty cells
                var dataIdx = -1;
                for (var c = 0; c < cellTexts.length; c++) {{
                    if (cellTexts[c].length > 1 && 
                        cellTexts[c].toLowerCase() !== 'satuan rp.' &&
                        cellTexts[c].indexOf('Laporan Publikasi') < 0) {{
                        dataIdx = c;
                        break;
                    }}
                }}
                
                if (dataIdx < 0) continue;
                
                pos = cellTexts[dataIdx];
                // Values are typically the last 2 cells
                val1 = cellTexts.length > dataIdx + 1 ? cellTexts[dataIdx + 1] : '';
                val2 = cellTexts.length > dataIdx + 2 ? cellTexts[dataIdx + 2] : '';
                
                // Skip non-data rows
                if (pos.toLowerCase() === 'pos' || pos.indexOf('Posisi') === 0 ||
                    pos.indexOf('Laporan keuangan tahunan') >= 0 ||
                    pos.indexOf('Informasi keuangan') >= 0 ||
                    pos.indexOf('Laporan Keuangan') >= 0) continue;
                
                results.push({{pos: pos, v1: val1, v2: val2}});
            }}
            
            return results;
        """)
        
        if not data:
            return []
        
        return [
            {
                'pos': r['pos'],
                'nilai_periode': self._clean_num(r.get('v1', '')),
                'nilai_tahun_sebelumnya': self._clean_num(r.get('v2', ''))
            }
            for r in data if r.get('pos')
        ]

    def _extract_kualitas_aset(self, iframe_idx: int) -> List[Dict]:
        """Extract Kualitas Aset data (Pos, L, DPK, KL, D, M, Jumlah) from iframe.
        
        Same strategy: find oReportDiv, then the largest table.
        This table has 8 columns: (empty), Pos, L, DPK, KL, D, M, Jumlah.
        """
        data = self._js(f"""
            var area = document.getElementById('ReportViewerArea');
            var iframes = area.getElementsByTagName('iframe');
            if ({iframe_idx} >= iframes.length) return [];
            
            var doc = iframes[{iframe_idx}].contentDocument || iframes[{iframe_idx}].contentWindow.document;
            
            var reportDiv = doc.querySelector('[id*="oReportDiv"]');
            if (!reportDiv) return [];
            
            // Find largest table by row count
            var allTables = reportDiv.getElementsByTagName('table');
            var dataTable = null;
            var maxRows = 0;
            
            for (var t = 0; t < allTables.length; t++) {{
                if (allTables[t].rows.length > maxRows) {{
                    maxRows = allTables[t].rows.length;
                    dataTable = allTables[t];
                }}
            }}
            
            if (!dataTable || maxRows < 5) return [];
            
            var results = [];
            var trs = dataTable.rows;
            
            for (var r = 0; r < trs.length; r++) {{
                var cells = trs[r].cells;
                if (!cells || cells.length < 7) continue;
                
                var cellTexts = [];
                for (var c = 0; c < cells.length; c++) {{
                    var txt = cells[c].innerText || '';
                    cellTexts.push(txt.trim().split(String.fromCharCode(10)).join(' '));
                }}
                
                // Find the pos name (first non-empty, non-header cell)
                var pos = '';
                var dataStart = -1;
                for (var c = 0; c < cellTexts.length; c++) {{
                    var t = cellTexts[c];
                    if (t.length > 1 && t.toLowerCase() !== 'satuan rp.' &&
                        t.indexOf('Laporan Publikasi') < 0 &&
                        t.toLowerCase() !== 'pos') {{
                        pos = t;
                        dataStart = c;
                        break;
                    }}
                }}
                
                if (!pos || dataStart < 0) continue;
                if (pos.indexOf('Nominal Dalam') >= 0 || pos.indexOf('Laporan keuangan') >= 0 ||
                    pos.indexOf('Informasi keuangan') >= 0) continue;
                
                // Skip header rows (L | DPK | KL | D | M | Jumlah)
                var joined = cellTexts.join(' ').toLowerCase();
                if (joined.indexOf('dpk') >= 0 && joined.indexOf('jumlah') >= 0) continue;
                
                // Values follow the pos: L, DPK, KL, D, M, Jumlah
                var vals = cellTexts.slice(dataStart + 1);
                // Filter out empty-string vals except keep numerics and zeros
                while (vals.length < 6) vals.push('');
                if (vals.length > 6) vals = vals.slice(vals.length - 6);
                
                results.push({{
                    pos: pos,
                    l: vals[0], dpk: vals[1], kl: vals[2],
                    d: vals[3], m: vals[4], jumlah: vals[5]
                }});
            }}
            
            return results;
        """)
        
        if not data:
            return []
        
        return [
            {
                'pos': r['pos'],
                'nilai_l': self._clean_num(r.get('l', '')),
                'nilai_dpk': self._clean_num(r.get('dpk', '')),
                'nilai_kl': self._clean_num(r.get('kl', '')),
                'nilai_d': self._clean_num(r.get('d', '')),
                'nilai_m': self._clean_num(r.get('m', '')),
                'nilai_jumlah': self._clean_num(r.get('jumlah', '')),
            }
            for r in data if r.get('pos')
        ]

    def _clean_num(self, val: str) -> str:
        """Clean a numeric string from Indonesian formatting."""
        if not val or val.strip() in ('-', '', 'N/A'):
            return '0'
        return val.replace('\xa0', '').replace(' ', '').strip()

    def _has_error_status(self) -> bool:
        status = self._js(
            "var s = document.getElementById('ReportStatus'); return s ? s.innerText : '';"
        )
        if not status: return False
        return 'tidak tersedia' in status.lower() or 'error' in status.lower()

    # ── High-Level Scoping ───────────────────────────────────
    def scrape_metadata(self):
        """Scrape all provinces, cities, and banks into DB."""
        logger.info("═══ Starting Metadata Scrape ═══")
        self.open_page()
        
        provinces = self.get_dropdown_options(config.EXTJS_IDS["province"])
        for p in provinces:
            self.db.save_provinsi(p["value"], p["text"])
            self.select_province(p["value"])
            
            cities = self.get_dropdown_options(config.EXTJS_IDS["city"])
            for c in cities:
                self.db.save_kabupaten(c["value"], c["text"], p["value"])
                self.select_city(c["value"])
                
                banks = self.get_dropdown_options(config.EXTJS_IDS["bank"])
                for b in banks:
                    self.db.save_bank(b["value"], b["text"], c["value"], p["value"])
                    
        logger.info("═══ Metadata Scrape Complete ═══")

    def scrape_reports(self, bulan: str, tahun: str, max_banks: Optional[int] = None, prov_code: Optional[str] = None, city_code: Optional[str] = None):
        """Scrape reports for all banks stored in DB."""
        logger.info(f"═══ Starting Report Scrape: {bulan} {tahun} ═══")
        
        query = """
            SELECT b.code, b.nama, b.kabupaten_code, b.provinsi_code,
                   k.nama as city_name, p.nama as prov_name
            FROM bank b
            JOIN kabupaten k ON b.kabupaten_code = k.code
            JOIN provinsi p ON b.provinsi_code = p.code
            WHERE 1=1
        """
        params = []
        if prov_code:
            query += " AND b.provinsi_code = ?"
            params.append(prov_code)
        if city_code:
            query += " AND b.kabupaten_code = ?"
            params.append(city_code)
            
        banks = self.db.conn.execute(query, params).fetchall()
        
        stats = {"done": 0, "skipped": 0, "no_data": 0, "error": 0}
        total = 0
        
        for b_code, b_name, c_code, p_code, c_name, p_name in banks:
            if max_banks and total >= max_banks: break
            
            logger.info(f"Bank [{total+1}/{len(banks)}]: {b_name} ({c_name}, {p_name})")
            
            # Skip if all reports already done
            all_done = True
            for rid in config.REPORT_TYPES.keys():
                if not self.db.is_scraped(bulan, tahun, p_code, c_code, b_code, rid):
                    all_done = False; break
            if all_done:
                logger.info("  ✓ Already scraped.")
                stats["skipped"] += 1; total += 1; continue

            try:
                # Fresh page per bank to avoid state contamination
                self.open_page()
                self.set_period(bulan, tahun)
                self.select_province(p_code)
                self.select_city(c_code)
                self.select_bank(b_code, b_name)
                self.check_all_reports()
                
                # Debug screenshot for first bank
                if total == 0:
                    self.driver.save_screenshot("debug_reports_checked.png")
                    logger.info("Saved debug screenshot")
                
                if not self.click_tampilkan():
                    stats["error"] += 1
                    total += 1
                    continue
                    
                if self._has_error_status():
                    logger.warning("  ✗ Data unavailable.")
                    for rid in config.REPORT_TYPES.keys():
                        self.db.mark_scraped(bulan, tahun, p_code, c_code, b_code, rid, "no_data")
                    stats["no_data"] += 1
                else:
                    data = self.parse_report_tables()
                    if data:
                        for rid, rows in data.items():
                            if rid == 'BPK-901-000003':
                                # Kualitas Aset uses separate table with 6 value columns
                                self.db.save_kualitas_aset_rows(
                                    bulan, tahun, p_code, c_code, b_code, rows
                                )
                            else:
                                self.db.save_laporan_rows(
                                    bulan, tahun, p_code, c_code, b_code, rid, rows
                                )
                            self.db.mark_scraped(bulan, tahun, p_code, c_code, b_code, rid, "done")
                        stats["done"] += 1
                        logger.info(f"  ✓ Extracted {len(data)} reports, {sum(len(r) for r in data.values())} rows.")
                    else:
                        logger.warning("  ✗ No tables found.")
                        for rid in config.REPORT_TYPES.keys():
                            self.db.mark_scraped(bulan, tahun, p_code, c_code, b_code, rid, "no_data")
                        stats["no_data"] += 1
                        
            except Exception as e:
                logger.error(f"  ✗ Error: {e}", exc_info=True)
                stats["error"] += 1
            
            total += 1
            
        logger.info(f"Report scrape complete: {stats}")
        return stats
