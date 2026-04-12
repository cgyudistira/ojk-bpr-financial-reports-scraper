"""
Inspect the actual table structure from each of the 5 OJK report iframes.
Shows headers, column count, row count, and sample data for each report type.
"""
from src.scraper import OJKScraper
from src.database import Database
import time
import sys

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
result = s.click_tampilkan()
print(f"click_tampilkan: {result}")

if not result:
    print("FAILED to render reports!")
    s.driver.quit()
    db.close()
    exit(1)

# Wait extra for iframes to fully load
time.sleep(10)

# Extract detailed table info from each iframe
for idx in range(5):
    data = s.driver.execute_script(f"""
        var area = document.getElementById('ReportViewerArea');
        if (!area) return null;
        var iframes = area.getElementsByTagName('iframe');
        if ({idx} >= iframes.length) return null;
        
        var doc = iframes[{idx}].contentDocument || iframes[{idx}].contentWindow.document;
        
        // Find the report title
        var title = '';
        var spans = doc.getElementsByTagName('span');
        for (var i = 0; i < spans.length; i++) {{
            var t = spans[i].innerText.trim();
            if (t.indexOf('Laporan') === 0 && t.length > 10) {{
                title = t;
                break;
            }}
        }}
        
        // Find all data tables (skip navigation/toolbar tables)
        // The main data table usually has cells with financial data
        var allTables = doc.getElementsByTagName('table');
        var dataTables = [];
        
        for (var t = 0; t < allTables.length; t++) {{
            var tbl = allTables[t];
            var rows = tbl.getElementsByTagName('tr');
            if (rows.length < 3) continue;  // Skip tiny tables
            
            // Check if table has numeric financial data
            var hasNumbers = false;
            var cells = tbl.getElementsByTagName('td');
            for (var c = 0; c < Math.min(cells.length, 50); c++) {{
                var txt = cells[c].innerText.trim();
                if (/^[\\d,\\.]+$/.test(txt) && txt.length > 2) {{
                    hasNumbers = true;
                    break;
                }}
            }}
            
            if (hasNumbers) {{
                var tableRows = [];
                for (var r = 0; r < Math.min(rows.length, 25); r++) {{
                    var rowCells = rows[r].children;
                    var cellTexts = [];
                    for (var c = 0; c < rowCells.length; c++) {{
                        cellTexts.push(rowCells[c].innerText.trim().substring(0, 60));
                    }}
                    tableRows.push(cellTexts);
                }}
                dataTables.push({{
                    rowCount: rows.length,
                    colCount: rows[0] ? rows[0].children.length : 0,
                    sample: tableRows
                }});
            }}
        }}
        
        return {{
            title: title,
            totalTables: allTables.length,
            dataTables: dataTables.length,
            tables: dataTables
        }};
    """)
    
    if not data:
        print(f"\nIframe {idx}: NO DATA")
        continue
    
    print(f"\n{'=' * 80}")
    print(f"IFRAME {idx}: {data['title']}")
    print(f"Total HTML tables: {data['totalTables']}, Data tables found: {data['dataTables']}")
    print(f"{'=' * 80}")
    
    for ti, tbl in enumerate(data.get('tables', [])):
        print(f"\n  --- Data Table {ti+1} ({tbl['rowCount']} rows x {tbl['colCount']} cols) ---")
        for ri, row_data in enumerate(tbl.get('sample', [])):
            label = "HDR" if ri < 2 else f"R{ri-1:02d}"
            print(f"  [{label}] {' | '.join(row_data)}")
        if tbl['rowCount'] > 25:
            print(f"  ... ({tbl['rowCount'] - 25} more rows)")

s.driver.quit()
db.close()
