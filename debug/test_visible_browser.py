"""
Debug: Compare our POST with a successful manual browser submission.
Open in NON-headless mode, manually click 'Tampilkan', capture the POST data.
"""
from src.scraper import OJKScraper
from src.database import Database
import time
import urllib.parse

db = Database()
s = OJKScraper(db, headless=False)  # VISIBLE browser
s.setup_browser()
s.open_page()
s.set_period('Desember', '2024')

# Use native dropdown click (which triggers server postback)
s.select_province('DATI01126')
s.select_city('DATI01573')
s.select_bank('600083')

time.sleep(2)

# BEFORE checking anything, let's see what ProvinceCode/CityCode input field contains
pre_check = s.driver.execute_script("""
    var results = {};
    var all = document.querySelectorAll('input');
    for (var i = 0; i < all.length; i++) {
        var n = all[i].name || all[i].id;
        if (n && (n.indexOf('Province') > -1 || n.indexOf('City') > -1 || n.indexOf('Bank') > -1)) {
            results[n] = {value: all[i].value, type: all[i].type};
        }
    }
    return results;
""")
print("=== INPUT FIELDS (before check) ===")
for k, v in pre_check.items():
    print(f"  {k}: value={v['value']}, type={v['type']}")

# Now use onCheckChange (the fixed method)
s.check_all_reports()

# Intercept POST
s.driver.execute_script("""
    window._postBody = null;
    window._respText = null;
    window._respStatus = null;
    var origSend = XMLHttpRequest.prototype.send;
    var origOpen = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function(method, url) {
        origOpen.apply(this, arguments);
        this.addEventListener('load', function() {
            window._respText = this.responseText;
            window._respStatus = this.status;
        });
    };
    XMLHttpRequest.prototype.send = function(data) {
        window._postBody = data;
        origSend.apply(this, arguments);
    };
""")

# FIX INPUTS before click like click_tampilkan does
s.driver.execute_script("""
    var prov = Ext.getCmp('ProvinceCode');
    if (prov) prov.inputEl.dom.value = prov.getValue();
    var city = Ext.getCmp('CityCode');
    if (city) city.inputEl.dom.value = city.getValue();
    
    var btn = Ext.getCmp('ShowReportButton');
    if (btn) btn.getEl().dom.click();
""")

time.sleep(8)

post_body = s.driver.execute_script('return window._postBody;')
status = s.driver.execute_script('return window._respStatus;')
resp = s.driver.execute_script('return window._respText;')

print(f"\n=== SERVER RESPONSE STATUS: {status} ===")

if post_body:
    # Save full post body for reference
    with open('debug/post_body_dump.txt', 'w') as f:
        f.write(post_body)
    print("Full POST body saved to debug/post_body_dump.txt")

if resp and status != 200:
    import re
    title = re.search(r'<title>(.*?)</title>', resp)
    if title:
        print(f"ERROR: {title.group(1)}")
    pre = re.search(r'<pre[^>]*>(.*?)</pre>', resp, re.DOTALL)
    if pre:
        print(pre.group(1)[:500])

if status == 200:
    print("SUCCESS! Report rendered!")
    # Check area
    area = s.driver.execute_script("""
        var a = document.getElementById('ReportViewerArea');
        if (!a) return 'NO AREA';
        return {
            htmlLen: a.innerHTML.length,
            tables: a.getElementsByTagName('table').length,
            iframes: a.getElementsByTagName('iframe').length,
            text: a.innerText.substring(0, 300)
        };
    """)
    print("[ReportViewerArea]:", area)

# Keep browser open for manual inspection
input("Press Enter to close browser...")
s.driver.quit()
