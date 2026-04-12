"""
End-to-end test using the actual OJKScraper methods (with both fixes applied).
"""
from src.scraper import OJKScraper
from src.database import Database
import time
import urllib.parse

db = Database()
s = OJKScraper(db, headless=True)
s.setup_browser()
s.open_page()
s.set_period('Desember', '2024')
s.select_province('DATI01126')
s.select_city('DATI01573')
s.select_bank('600083')
s.check_all_reports()

# Intercept XHR to see what's sent
s.driver.execute_script("""
    window._postBody = null;
    window._respText = null;
    var origSend = XMLHttpRequest.prototype.send;
    var origOpen = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function(method, url) {
        origOpen.apply(this, arguments);
        this.addEventListener('load', function() {
            window._respText = this.responseText;
        });
    };
    XMLHttpRequest.prototype.send = function(data) {
        window._postBody = data;
        origSend.apply(this, arguments);
    };
""")

# Use the ACTUAL scraper method (with the DATI code fix)
s.click_tampilkan()

# Get post data
post_body = s.driver.execute_script('return window._postBody;')
if post_body:
    params = urllib.parse.parse_qs(post_body, keep_blank_values=True)
    print("=== KEY POST PARAMS ===")
    for key in ['ProvinceCode', 'CityCode', 'BankCode', 'Month', 'Year']:
        val = params.get(key, ['NOT FOUND'])[0]
        print(f"  {key} = {val}")

resp = s.driver.execute_script('return window._respText;')
if resp:
    import re
    title = re.search(r'<title>(.*?)</title>', resp)
    if title:
        print(f"\nSERVER ERROR: {title.group(1)}")
    elif len(resp) > 100:
        print(f"\nRESPONSE (first 300): {resp[:300]}")
    else:
        print(f"\nFULL RESPONSE: {resp}")

# Check area
area = s.driver.execute_script("""
    var a = document.getElementById('ReportViewerArea');
    if (!a) return 'NO AREA';
    var tables = a.getElementsByTagName('table');
    var iframes = a.getElementsByTagName('iframe');
    return {
        htmlLen: a.innerHTML.length,
        tables: tables.length,
        iframes: iframes.length,
        text: a.innerText.substring(0, 300)
    };
""")
print("\n[ReportViewerArea]:", area)

s.driver.save_screenshot('debug/test_e2e_result.png')
print("Screenshot saved.")
s.driver.quit()
