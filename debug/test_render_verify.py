"""
End-to-end test: Verify report rendering with the native onCheckChange fix.
"""
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
s.check_all_reports()

# Verify hidden field is now in JSON SubmittedNode format
hidden_val = s.driver.execute_script("""
    var inputs = document.getElementsByName('ReportTree_CheckNodes');
    return inputs.length > 0 ? inputs[0].value.substring(0, 200) : 'NOT FOUND';
""")
print("[CheckNodes format preview]:", hidden_val)

# Intercept XHR response
s.driver.execute_script("""
    window._xhrResp = [];
    var origOpen = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function(method, url) {
        origOpen.apply(this, arguments);
        this.addEventListener('load', function() {
            window._xhrResp.push({status: this.status, text: this.responseText.substring(0, 500)});
        });
    };
""")

# Click Display
s.driver.execute_script("""
    var btn = Ext.getCmp('ShowReportButton');
    if (btn) btn.getEl().dom.click();
""")
print("Clicked ShowReportButton, waiting 15s for render...")
time.sleep(15)

# Check XHR response
responses = s.driver.execute_script('return window._xhrResp;')
for i, r in enumerate(responses):
    print(f"\n--- XHR RESP {i} (status={r['status']}) ---")
    print(r['text'][:500])

# Check ReportViewerArea for content
area = s.driver.execute_script("""
    var a = document.getElementById('ReportViewerArea');
    if (!a) return 'NO AREA';
    var tables = a.getElementsByTagName('table');
    var iframes = a.getElementsByTagName('iframe');
    return {
        htmlLen: a.innerHTML.length,
        tables: tables.length,
        iframes: iframes.length,
        text: a.innerText.substring(0, 500)
    };
""")
print("\n[ReportViewerArea]:", area)

s.driver.save_screenshot('debug/test_render_result.png')
print("\nScreenshot saved to debug/test_render_result.png")
s.driver.quit()
