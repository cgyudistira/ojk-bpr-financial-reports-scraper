"""
Compact report structure inspector - shows headers and first 8 data rows per report.
"""
from src.scraper import OJKScraper
from src.database import Database
import time, sys, json

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
    "Laporan Posisi Keuangan (Balance Sheet)",
    "Laporan Laba Rugi (Profit & Loss)",
    "Laporan Kualitas Aset Produktif (Asset Quality)",
    "Laporan Komitmen dan Kontinjensi (Commitments)",
    "Laporan Informasi Lainnya (Other Info)",
]

for idx in range(5):
    data = s.driver.execute_script("""
        var area = document.getElementById('ReportViewerArea');
        var iframes = area.getElementsByTagName('iframe');
        var doc = iframes[%d].contentDocument || iframes[%d].contentWindow.document;
        
        // Find the MAIN data table - it's the one inside a div with specific SSRS structure
        // Look for table rows that have 'Pos' as header
        var allTables = doc.getElementsByTagName('table');
        var bestTable = null;
        var bestScore = 0;
        
        for (var t = 0; t < allTables.length; t++) {
            var tbl = allTables[t];
            var rows = tbl.getElementsByTagName('tr');
            if (rows.length < 5) continue;
            
            // Score by how many rows have financial-looking data
            var score = 0;
            for (var r = 0; r < rows.length; r++) {
                var cells = rows[r].children;
                for (var c = 0; c < cells.length; c++) {
                    var txt = cells[c].innerText.trim();
                    if (/^[\\d,\\.]+$/.test(txt) && txt.length > 1) score++;
                    if (txt.indexOf('Pos') === 0 || txt.indexOf('AKTIVA') >= 0 || 
                        txt.indexOf('PASIVA') >= 0 || txt.indexOf('PENDAPATAN') >= 0) score += 5;
                }
            }
            if (score > bestScore) { bestScore = score; bestTable = tbl; }
        }
        
        if (!bestTable) return {error: 'no data table found', totalTables: allTables.length};
        
        var rows = bestTable.getElementsByTagName('tr');
        var result = [];
        for (var r = 0; r < Math.min(rows.length, 12); r++) {
            var cells = rows[r].children;
            var row = [];
            for (var c = 0; c < cells.length; c++) {
                row.push(cells[c].innerText.trim().replace(/\\n/g, ' ').substring(0, 50));
            }
            result.push(row);
        }
        return {totalRows: rows.length, colCount: rows[0] ? rows[0].children.length : 0, sample: result, totalTables: allTables.length};
    """ % (idx, idx))
    
    print(f"\n{'=' * 80}")
    print(f"[{idx+1}] {REPORT_NAMES[idx]}")
    print(f"{'=' * 80}")
    
    if 'error' in data:
        print(f"  ERROR: {data['error']} (total tables: {data['totalTables']})")
        continue
    
    print(f"  Rows: {data['totalRows']}, Columns: {data['colCount']}")
    print()
    for ri, row in enumerate(data['sample']):
        tag = "HEADER" if ri < 2 else f"Row {ri-1}"
        cols = " | ".join(row)
        print(f"  [{tag:>8}] {cols}")
    if data['totalRows'] > 12:
        print(f"  ... +{data['totalRows'] - 12} more rows")

s.driver.quit()
db.close()
