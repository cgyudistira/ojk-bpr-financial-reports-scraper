"""
Deep DOM inspection: See what tables exist in iframe 0 and their structure.
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

# Deep inspect iframe 0
for iframe_idx in [0, 2]:
    print(f"\n{'='*80}")
    print(f"IFRAME {iframe_idx} DOM ANALYSIS")
    print(f"{'='*80}")
    
    info = s.driver.execute_script(f"""
        var area = document.getElementById('ReportViewerArea');
        var iframes = area.getElementsByTagName('iframe');
        var doc = iframes[{iframe_idx}].contentDocument || iframes[{iframe_idx}].contentWindow.document;
        
        var allTables = doc.getElementsByTagName('table');
        var tableInfo = [];
        
        for (var t = 0; t < allTables.length; t++) {{
            var tbl = allTables[t];
            var trs = tbl.rows;
            
            // Get first 3 rows content preview
            var preview = [];
            for (var r = 0; r < Math.min(trs.length, 3); r++) {{
                var cells = trs[r].cells;
                var cellTexts = [];
                for (var c = 0; c < cells.length; c++) {{
                    cellTexts.push(cells[c].innerText.trim().substring(0, 40));
                }}
                preview.push(cellTexts.join(' | '));
            }}
            
            // Check if table has id or class
            tableInfo.push({{
                idx: t,
                id: tbl.id || '',
                className: (tbl.className || '').substring(0, 50),
                rows: trs.length,
                cols: trs[0] ? trs[0].cells.length : 0,
                parentId: tbl.parentElement ? (tbl.parentElement.id || '').substring(0, 50) : '',
                parentClass: tbl.parentElement ? (tbl.parentElement.className || '').substring(0, 50) : '',
                preview: preview
            }});
        }}
        
        // Also check for divs with report-like IDs 
        var reportDivs = doc.querySelectorAll('[id*="oReportDiv"], [id*="ReportDiv"], [id*="VisibleReportContent"]');
        var divInfo = [];
        for (var d = 0; d < reportDivs.length; d++) {{
            divInfo.push({{
                id: reportDivs[d].id,
                tag: reportDivs[d].tagName,
                children: reportDivs[d].children.length,
                textLen: reportDivs[d].innerText.length
            }});
        }}
        
        return {{tables: tableInfo, reportDivs: divInfo}};
    """)
    
    print(f"\nReport Divs: {len(info.get('reportDivs', []))}")
    for d in info.get('reportDivs', []):
        print(f"  {d['tag']}#{d['id']} - children={d['children']}, textLen={d['textLen']}")
    
    print(f"\nTables: {len(info['tables'])}")
    for t in info['tables']:
        has_data = t['rows'] > 5
        marker = " ***" if has_data else ""
        print(f"\n  Table[{t['idx']}]{marker}: {t['rows']}r x {t['cols']}c | id='{t['id']}' class='{t['className']}'")
        print(f"    parent: id='{t['parentId']}' class='{t['parentClass']}'")
        for p in t['preview'][:2]:
            print(f"    > {p}")

s.driver.quit()
db.close()
