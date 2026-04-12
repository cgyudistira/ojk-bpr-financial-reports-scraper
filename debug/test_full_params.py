"""
Debug: Dump every single POST parameter to find what causes 'Length cannot be less than zero'.
The ProvinceCode/CityCode are now correct, so the issue is elsewhere.
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

# Intercept
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

# Fix inputs and click
s.driver.execute_script("""
    var prov = Ext.getCmp('ProvinceCode');
    if (prov) prov.inputEl.dom.value = prov.getValue();
    var city = Ext.getCmp('CityCode');
    if (city) city.inputEl.dom.value = city.getValue();
    
    var btn = Ext.getCmp('ShowReportButton');
    if (btn) btn.getEl().dom.click();
""")

time.sleep(5)

post_body = s.driver.execute_script('return window._postBody;')
if post_body:
    params = urllib.parse.parse_qs(post_body, keep_blank_values=True)
    print("=== ALL POST PARAMETERS ===")
    for key in sorted(params.keys()):
        val = params[key][0]
        # Truncate long values
        disp = val[:300] + '...' if len(val) > 300 else val
        print(f"  [{len(val):5d}] {key} = {disp}")

resp = s.driver.execute_script('return window._respText;')
if resp:
    import re
    title = re.search(r'<title>(.*?)</title>', resp)
    print(f"\n=== SERVER RESPONSE: {title.group(1) if title else 'OK'} ===")
    # Extract stack trace
    pre = re.search(r'<pre[^>]*>(.*?)</pre>', resp, re.DOTALL)
    if pre:
        print(pre.group(1)[:600])

s.driver.quit()
