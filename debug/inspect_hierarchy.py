"""Inspect how SSRS report encodes hierarchy in Iframe 1 (e.g. padding, bold text, &nbsp;)"""
from src.scraper import OJKScraper
from src.database import Database
import time, sys, json

sys.stdout.reconfigure(encoding='utf-8')
db = Database(); db.connect()
row = db.conn.execute("SELECT nama FROM bank WHERE code = '600083'").fetchone()

s = OJKScraper(db, headless=True)
s.setup_browser()
s.open_page()
s.set_period('Desember', '2024')
s.select_province('DATI01126')
s.select_city('DATI01573')
s.select_bank('600083', row[0])
s.check_all_reports()
s.click_tampilkan()
time.sleep(12)

# Extract raw row info from Iframe 1 to see styles/padding/nbsps
script = """
    var doc = document.getElementById('ReportViewerArea').getElementsByTagName('iframe')[1].contentDocument;
    var rd = doc.querySelector('[id*=oReportDiv]');
    var tables = rd.getElementsByTagName('table');
    var maxR = 0; var dataTable = null;
    for(var t=0; t<tables.length; t++) {
        if(tables[t].rows.length > maxR) {
            maxR = tables[t].rows.length;
            dataTable = tables[t];
        }
    }
    
    var info = [];
    for(var r=0; r<Math.min(15, dataTable.rows.length); r++) {
        var cell = dataTable.rows[r].cells[0];
        if(!cell) continue;
        
        var innerHTML = cell.innerHTML;
        var innerText = cell.innerText;
        var textContent = cell.textContent;
        var style = window.getComputedStyle(cell);
        // Sometimes SSRS puts the text in an inner DIV
        var childDiv = cell.querySelector('div');
        var childStyle = childDiv ? window.getComputedStyle(childDiv) : null;
        
        info.push({
            rowIdx: r,
            rawHtml: innerHTML.substring(0, 100),
            innerText: innerText,
            textContent: textContent,
            fontStyle: childStyle ? childStyle.fontWeight : style.fontWeight,
            paddingLeft: childStyle ? childStyle.paddingLeft : style.paddingLeft,
            marginLeft: childStyle ? childStyle.marginLeft : style.marginLeft
        });
    }
    return info;
"""
info = s.driver.execute_script(script)

print("=== HIERARCHY TEST RESULTS ===")
for r in info:
    print(f"Row {r['rowIdx']}:")
    print(f"  Inner Text : '{r['innerText']}'")
    print(f"  TextContent: '{r['textContent']}'")
    print(f"  Weight     : {r['fontStyle']}")
    print(f"  Padding L  : {r['paddingLeft']}")
    print(f"  Margin L   : {r['marginLeft']}")
    print(f"  Raw HTML   : {r['rawHtml']}")
    print("-" * 50)

s.driver.quit(); db.close()
