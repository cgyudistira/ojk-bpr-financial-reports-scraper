"""
Quick debug: check the actual data table for iframe 1 (Laba Rugi) and iframe 2 (Kualitas Aset)
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

# Check iframe 1 (Laba Rugi) - why no data?
for iframe_idx in [1, 2]:
    print(f"\n{'='*80}")
    print(f"IFRAME {iframe_idx}")
    print(f"{'='*80}")
    
    info = s.driver.execute_script(f"""
        var area = document.getElementById('ReportViewerArea');
        var iframes = area.getElementsByTagName('iframe');
        var doc = iframes[{iframe_idx}].contentDocument || iframes[{iframe_idx}].contentWindow.document;
        
        // Check for oReportDiv
        var reportDiv = doc.querySelector('[id*="oReportDiv"]');
        if (!reportDiv) return {{error: 'no oReportDiv found'}};
        
        // Find ALL tables and list sizes
        var allTables = reportDiv.getElementsByTagName('table');
        var tableList = [];
        for (var t = 0; t < allTables.length; t++) {{
            tableList.push({{idx: t, rows: allTables[t].rows.length, cols: allTables[t].rows[0] ? allTables[t].rows[0].cells.length : 0}});
        }}
        
        // Find the largest table
        var largest = null;
        var maxR = 0;
        for (var t = 0; t < allTables.length; t++) {{
            if (allTables[t].rows.length > maxR) {{
                maxR = allTables[t].rows.length;
                largest = allTables[t];
            }}
        }}
        
        // Show first 5 rows of largest
        var sample = [];
        if (largest) {{
            for (var r = 0; r < Math.min(largest.rows.length, 8); r++) {{
                var cells = largest.rows[r].cells;
                var row = [];
                for (var c = 0; c < cells.length; c++) {{
                    row.push(cells[c].innerText.trim().substring(0, 45));
                }}
                sample.push(row);
            }}
        }}
        
        // Check page count
        var pageInfo = doc.querySelector('[id*="ctl05_ctl00_CurrentPage"]');
        var totalPages = doc.querySelector('[id*="ctl05_ctl00_TotalPages"]');
        
        return {{
            tables: tableList.length,
            tableDetails: tableList.filter(function(t) {{ return t.rows > 3; }}),
            largestRows: maxR,
            sample: sample,
            currentPage: pageInfo ? pageInfo.value : 'N/A',
            totalPages: totalPages ? totalPages.innerText : 'N/A'
        }};
    """)
    
    print(f"  Tables with >3 rows: {info.get('tableDetails', [])}")
    print(f"  Largest table: {info.get('largestRows')} rows")
    print(f"  Page: {info.get('currentPage')} of {info.get('totalPages')}")
    print(f"\n  Sample rows from largest table:")
    for i, row in enumerate(info.get('sample', [])):
        print(f"    [{i}] {' | '.join(row)}")

s.driver.quit()
db.close()
