"""Quick debug: test extraction on iframe 1 directly."""
from src.scraper import OJKScraper
from src.database import Database
import time, sys

sys.stdout.reconfigure(encoding='utf-8')
db = Database(); db.connect()
row = db.conn.execute("SELECT nama FROM bank WHERE code = '600083'").fetchone()
s = OJKScraper(db, headless=True); s.setup_browser(); s.open_page()
s.set_period('Desember', '2024'); s.select_province('DATI01126')
s.select_city('DATI01573'); s.select_bank('600083', row[0])
s.check_all_reports(); s.click_tampilkan(); time.sleep(12)

# Direct test: what does _extract_standard_report get for iframe 1?
data = s._extract_standard_report(1)
print(f'Iframe 1 extracted: {len(data)} rows')
for r in data[:5]:
    print(f'  {r}')

# Also check: does oReportDiv exist and what tables does it contain?
check = s.driver.execute_script("""
    var area = document.getElementById('ReportViewerArea');
    var iframes = area.getElementsByTagName('iframe');
    var doc = iframes[1].contentDocument;
    var rd = doc.querySelector('[id*=oReportDiv]');
    if (!rd) return 'NO REPORT DIV';
    var tables = rd.getElementsByTagName('table');
    var sizes = [];
    for (var i = 0; i < tables.length; i++) {
        sizes.push({idx: i, rows: tables[i].rows.length, cols: tables[i].rows[0]?tables[i].rows[0].cells.length:0});
    }
    return {divId: rd.id, tableCount: tables.length, sizes: sizes.filter(function(s){return s.rows > 2;})};
""")
print(f'Report div check: {check}')

s.driver.quit(); db.close()
