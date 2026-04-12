"""
End-to-end test with both critical fixes:
1. onCheckChange for ReportTree_CheckNodes (Ext.Net.SubmittedNode format)
2. BankCode in 'code-name' format (server Substring fix)
3. ProvinceCode/CityCode input values set to DATI codes
"""
from src.scraper import OJKScraper
from src.database import Database
import time

db = Database()
db.connect()

# Get bank name from database
row = db.conn.execute("SELECT nama FROM bank WHERE code = '600083'").fetchone()
bank_name = row[0] if row else "PT Bank Unknown"
print(f"Bank name from DB: {bank_name}")

s = OJKScraper(db, headless=True)
s.setup_browser()
s.open_page()
s.set_period('Desember', '2024')
s.select_province('DATI01126')
s.select_city('DATI01573')
s.select_bank('600083', bank_name)
s.check_all_reports()

# Intercept XHR
s.driver.execute_script("""
    window._respStatus = null;
    window._respText = null;
    var origOpen = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function(method, url) {
        origOpen.apply(this, arguments);
        this.addEventListener('load', function() {
            window._respStatus = this.status;
            window._respText = this.responseText;
        });
    };
""")

# Use the actual scraper method (which fixes province/city codes)
result = s.click_tampilkan()
print(f"\nclick_tampilkan returned: {result}")

status = s.driver.execute_script('return window._respStatus;')
resp = s.driver.execute_script('return window._respText;')

print(f"XHR Status: {status}")

if status and status != 200 and resp:
    import re
    title = re.search(r'<title>(.*?)</title>', resp)
    if title:
        print(f"SERVER ERROR: {title.group(1)}")
    pre = re.search(r'<pre[^>]*>(.*?)</pre>', resp, re.DOTALL)
    if pre:
        print(pre.group(1)[:500])
elif status == 200:
    print("SUCCESS! Server returned 200")

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
        text: a.innerText.substring(0, 500)
    };
""")
print(f"\n[ReportViewerArea]: {area}")

s.driver.save_screenshot('debug/test_final_result.png')
print("Screenshot saved to debug/test_final_result.png")
s.driver.quit()
db.close()
