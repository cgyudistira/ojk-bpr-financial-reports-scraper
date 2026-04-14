from src.scraper import OJKScraper
from src.database import Database
import time, sys
sys.stdout.reconfigure(encoding='utf-8')
db = Database(); db.connect()
row = db.conn.execute("SELECT nama FROM bank WHERE code = '600083'").fetchone()
s = OJKScraper(db, headless=True)
s.setup_browser(); s.open_page(); s.set_period('Desember', '2024'); s.select_province('DATI01126'); s.select_city('DATI01573'); s.select_bank('600083', row[0])
s.check_all_reports(); s.click_tampilkan(); time.sleep(12)

script = """
    var doc = document.getElementById('ReportViewerArea').getElementsByTagName('iframe')[1].contentDocument;
    var rd = doc.querySelector('[id*=oReportDiv]');
    var tables = rd.getElementsByTagName('table');
    var maxR = 0; var dataTable = null;
    for(var t=0; t<tables.length; t++) {
        if(tables[t].rows.length > maxR) { maxR = tables[t].rows.length; dataTable = tables[t]; }
    }
    
    var info = [];
    for(var r=0; r<Math.min(10, dataTable.rows.length); r++) {
        var rowText = ''; var padding = ''; var weight = ''; var raw='';
        for(var c=0; c<dataTable.rows[r].cells.length; c++) {
            var cell = dataTable.rows[r].cells[c];
            if(cell.innerText.trim().length > 1) {
                rowText = cell.innerText;
                var style = window.getComputedStyle(cell);
                var div = cell.querySelector('div');
                var divStyle = div ? window.getComputedStyle(div) : null;
                padding = divStyle ? divStyle.paddingLeft : style.paddingLeft;
                weight = divStyle ? divStyle.fontWeight : style.fontWeight;
                raw = cell.innerHTML;
                break;
            }
        }
        info.push(r + ' | Text: ' + rowText.substring(0, 40).replace(/\\n/g, ' ') + ' | Pad: ' + padding + ' | Wgt: ' + weight + ' | Html: ' + raw.substring(0,60));
    }
    return info;
"""
try:
    info = s.driver.execute_script(script)
    for i in info: print(i)
except Exception as e:
    print('Error:', e)
s.driver.quit(); db.close()
