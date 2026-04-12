"""
Extract actual financial data rows from SSRS report iframes.
SSRS renders data in deeply nested table structures. The actual data cells
are usually inside elements with specific SSRS CSS classes.
"""
from src.scraper import OJKScraper
from src.database import Database
import time, sys

sys.stdout.reconfigure(encoding='utf-8')

db = Database()
db.connect()
row = db.conn.execute("SELECT nama FROM bank WHERE code = '600083'").fetchone()
bank_name = row[0] if row else ""

s = OJKScraper(db, headless=True)
s.setup_browser()
s.open_page()
s.set_period('Desember', '2024')
s.select_province('DATI01126')
s.select_city('DATI01573')
s.select_bank('600083', bank_name)
s.check_all_reports()
s.click_tampilkan()
time.sleep(12)

REPORT_NAMES = [
    "1. Laporan Posisi Keuangan (Balance Sheet)",
    "2. Laporan Laba Rugi (Profit & Loss)",
    "3. Laporan Kualitas Aset Produktif (Asset Quality)",
    "4. Laporan Komitmen dan Kontinjensi (Commitments)",
    "5. Laporan Informasi Lainnya (Other Info)",
]

for idx in range(5):
    # Extract the visible text from the SSRS report body, skipping toolbar
    data = s.driver.execute_script("""
        var area = document.getElementById('ReportViewerArea');
        var iframes = area.getElementsByTagName('iframe');
        var doc = iframes[%d].contentDocument || iframes[%d].contentWindow.document;
        
        // SSRS renders data inside a div with id containing 'oReportDiv'
        // or inside elements with specific classes
        var reportDiv = doc.querySelector('[id*="oReportDiv"]');
        if (!reportDiv) {
            // Fallback: get the main content area
            var divs = doc.querySelectorAll('div');
            for (var i = 0; i < divs.length; i++) {
                if (divs[i].id && divs[i].id.indexOf('oReportDiv') >= 0) {
                    reportDiv = divs[i];
                    break;
                }
            }
        }
        
        if (!reportDiv) {
            // Last fallback: use body but skip first elements (toolbar)
            reportDiv = doc.body;
        }
        
        // Find all tables inside the report div
        var tables = reportDiv.getElementsByTagName('table');
        var dataRows = [];
        
        for (var t = 0; t < tables.length; t++) {
            var tbl = tables[t];
            var trs = tbl.rows;
            if (trs.length < 3) continue;
            
            for (var r = 0; r < trs.length; r++) {
                var cells = trs[r].cells;
                if (cells.length < 2) continue;
                
                var rowData = [];
                var hasContent = false;
                for (var c = 0; c < cells.length; c++) {
                    var txt = cells[c].innerText.trim().replace(/\\n/g, ' ');
                    if (txt.length > 0) hasContent = true;
                    rowData.push(txt.substring(0, 55));
                }
                if (hasContent && rowData.join('').length > 3) {
                    dataRows.push(rowData);
                }
            }
        }
        
        // Deduplicate based on string content
        var seen = {};
        var unique = [];
        for (var i = 0; i < dataRows.length; i++) {
            var key = dataRows[i].join('|');
            if (!seen[key]) {
                seen[key] = true;
                unique.push(dataRows[i]);
            }
        }
        
        return unique;
    """ % (idx, idx))
    
    print(f"\n{'=' * 90}")
    print(f"{REPORT_NAMES[idx]}")
    print(f"{'=' * 90}")
    
    if not data:
        print("  No data extracted")
        continue
    
    # Filter out toolbar rows
    filtered = []
    for row in data:
        joined = ''.join(row).lower()
        if 'find' in joined and 'next' in joined:
            continue
        if len(joined.replace(' ', '')) < 2:
            continue
        filtered.append(row)
    
    print(f"  Total data rows: {len(filtered)}")
    print()
    
    # Show first 15 rows
    for ri, row in enumerate(filtered[:15]):
        cols = " | ".join(row)
        print(f"  [{ri+1:3d}] {cols}")
    
    if len(filtered) > 15:
        print(f"\n  ... +{len(filtered) - 15} more rows")

s.driver.quit()
db.close()
