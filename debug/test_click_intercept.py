from src.scraper import OJKScraper
from src.database import Database
import time

db = Database()
s = OJKScraper(db, headless=True)
s.setup_browser()
s.open_page()
s.set_period('Desember', '2024')
s.select_province('DATI01126')
s.select_city('DATI01573')
s.select_bank('600083')

# We override the check_all_reports to inject JSON.stringify
s.driver.execute_script("""
    var t = Ext.getCmp('ReportTree');
    var checked = [];
    t.getRootNode().cascadeBy(function(node) {
        if (node.get('id') !== 'root') {
            node.set('checked', true);
            checked.push(node.get('id'));
        }
    });
    var input = document.getElementsByName('ReportTree_CheckNodes');
    if (input.length > 0) {
        // Here we use JSON stringify because the server parser threw:
        // Unexpected character encountered while parsing value: B. Path '', line 0, position 0.
        input[0].value = JSON.stringify(checked); 
    }
""")

# Intercept XHR responses
s.driver.execute_script("""
    window._xhrResponses = [];
    var open = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function(method, url) {
        open.apply(this, arguments);
        this.addEventListener('load', function() {
            window._xhrResponses.push(this.responseText);
        });
    };
""")

print('Clicking ShowReportButton...')
s.driver.execute_script("""
    var btn = Ext.getCmp('ShowReportButton');
    if (btn) btn.getEl().dom.click();
""")

time.sleep(5)

res = s.driver.execute_script('return window._xhrResponses;')
try:
    for i, r in enumerate(res):
        print(f'--- RESP {i} ---')
        print(str(r)[:1000])
except Exception as e:
    print('Failed to print output:', e)

area_html = s.driver.execute_script('var a = document.getElementById("ReportViewerArea"); return a ? a.innerHTML : "";')
print('AREA HTML:', area_html[:1000])

s.driver.quit()
