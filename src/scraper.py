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
    def select_bank(self, code: str):
        """Select bank — BankCode is Ext.net.DropDownField, not a combo.
        It needs setValue() directly, no picker/store involved."""
        logger.info(f"Selecting bank: {code}")
        self._js(f"""
            var cmp = Ext.getCmp('BankCode');
            if (cmp) {{ cmp.setValue('{code}'); }}
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
        var checkedIds = [];
        t.getRootNode().cascadeBy(function(node) {
            if (node.isLeaf()) {
                var text = node.get('text');
                var rid = node.getId();
                if (!seen[text]) {
                    node.set('checked', true);
                    t.fireEvent('checkchange', node, true);
                    seen[text] = true;
                    checked++;
                    checkedIds.push(rid);
                } else {
                    node.set('checked', false);
                }
            }
        });
        
        // CRITICAL FIX: The ASP.NET server reads from 'ReportTree_CheckNodes' hidden field
        // ExtJS might not update it automatically when we use fireEvent
        var inputs = document.getElementsByName('ReportTree_CheckNodes');
        if (inputs.length > 0) {
            inputs[0].value = checkedIds.join(',');
        } else {
            // Create it if it doesn't exist
            var tdom = document.getElementById('ReportTree');
            if (tdom) {
                var input = document.createElement('input');
                input.type = 'hidden';
                input.name = 'ReportTree_CheckNodes';
                input.value = checkedIds.join(',');
                tdom.appendChild(input);
            }
        }
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
        """Extract report data from iframes in ReportViewerArea."""
        iframes_data = self._js("""
            var area = document.getElementById('ReportViewerArea');
            if (!area) return [];
            var iframes = area.getElementsByTagName('iframe');
            var results = [];
            for (var i=0; i<iframes.length; i++) {
                try {
                    var doc = iframes[i].contentDocument || iframes[i].contentWindow.document;
                    if (doc.body) {
                        results.push({ id: iframes[i].id, html: doc.body.innerHTML });
                    }
                } catch(e) {}
            }
            return results;
        """)
        
        if not iframes_data:
            html = self._js(
                "var a = document.getElementById('ReportViewerArea'); return a ? a.innerHTML : '';"
            )
            if html and len(html) > 100:
                iframes_data = [{"id": "direct", "html": html}]
            else:
                return {}

        results = {}
        for item in iframes_data:
            html = item.get("html", "")
            if not html or len(html) < 50:
                continue
                
            soup = BeautifulSoup(html, 'html.parser')
            tables = soup.find_all('table')
            
            report_id = None
            for table in tables:
                text = table.get_text(' ', strip=True).lower()
                det_id = self._detect_report_type(text)
                if det_id:
                    report_id = det_id
                
                rows = table.find_all('tr')
                if len(rows) < 3 or not report_id:
                    continue
                    
                parsed = self._parse_rows(rows)
                if parsed:
                    if report_id not in results:
                        results[report_id] = []
                    results[report_id].extend(parsed)
                    
        return results

    def _detect_report_type(self, text: str) -> Optional[str]:
        if 'posisi keuangan' in text or 'neraca' in text: return 'BPK-901-000001'
        if 'laba' in text and 'rugi' in text: return 'BPK-901-000002'
        if 'kualitas aset' in text or 'aktiva' in text: return 'BPK-901-000003'
        if 'komitmen' in text and 'kontinjensi' in text: return 'BPK-901-000004'
        if 'informasi lainnya' in text: return 'BPK-901-000005'
        return None

    def _parse_rows(self, rows) -> List[Dict]:
        data = []
        found_header = False
        for row in rows:
            cells = [c.get_text(strip=True) for c in row.find_all(['td', 'th'])]
            if len(cells) < 2: continue
            
            joined = ' '.join(cells).lower()
            if not found_header:
                if 'pos' in joined and ('tanggal' in joined or 'periode' in joined):
                    found_header = True
                continue
                
            pos = cells[0].strip()
            if not pos or pos.lower() in ('pos', 'no', 'satuan rp.'): continue
            
            v1 = self._clean_num(cells[1]) if len(cells) > 1 else '0'
            v2 = self._clean_num(cells[2]) if len(cells) > 2 else '0'
            
            data.append({'pos': pos, 'nilai_periode': v1, 'nilai_tahun_sebelumnya': v2})
        return data

    def _clean_num(self, val: str) -> str:
        if not val or val == '-': return '0'
        return val.replace('\xa0', '').replace(' ', '')

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
                self.select_bank(b_code)
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
                            self.db.save_laporan_rows(bulan, tahun, p_code, c_code, b_code, rid, rows)
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
