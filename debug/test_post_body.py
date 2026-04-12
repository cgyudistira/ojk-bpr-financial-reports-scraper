"""
Debug: Capture the FULL POST body sent when clicking ShowReportButton
to find which parameter causes 'Length cannot be less than zero'.
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

# Intercept the full POST data
s.driver.execute_script("""
    window._postBody = null;
    window._respBody = null;
    var origSend = XMLHttpRequest.prototype.send;
    var origOpen = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function(method, url) {
        origOpen.apply(this, arguments);
        this.addEventListener('load', function() {
            window._respBody = this.responseText;
        });
    };
    XMLHttpRequest.prototype.send = function(data) {
        window._postBody = data;
        origSend.apply(this, arguments);
    };
""")

# Click
s.driver.execute_script("""
    var btn = Ext.getCmp('ShowReportButton');
    if (btn) btn.getEl().dom.click();
""")
print("Clicked, waiting 5s...")
time.sleep(5)

post_body = s.driver.execute_script('return window._postBody;')
if post_body:
    # Parse the form-encoded data
    params = urllib.parse.parse_qs(post_body, keep_blank_values=True)
    print("=== ALL POST PARAMETERS ===")
    for key in sorted(params.keys()):
        val = params[key][0]
        if len(val) > 200:
            val = val[:200] + '...'
        print(f"  {key} = {val}")
else:
    print("No POST body captured!")

# Also print the response title for the error
resp = s.driver.execute_script('return window._respBody;')
if resp:
    import re
    title = re.search(r'<title>(.*?)</title>', resp)
    print(f"\n=== SERVER ERROR: {title.group(1) if title else 'unknown'} ===")
    # Look for more detail
    detail = re.search(r'<pre[^>]*>(.*?)</pre>', resp, re.DOTALL)
    if detail:
        print(detail.group(1)[:500])

s.driver.quit()
