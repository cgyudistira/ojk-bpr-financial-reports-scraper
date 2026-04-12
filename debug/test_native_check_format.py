"""
Debug script: Capture the exact POST payload format OJK server expects for ReportTree_CheckNodes.
Run this with headless=False so you can manually interact with the browser, or let it auto-click.
"""
from src.scraper import OJKScraper
from src.database import Database
import time

db = Database()
s = OJKScraper(db, headless=False)  # Non-headless to observe
s.setup_browser()
s.open_page()
s.set_period('Desember', '2024')
s.select_province('DATI01126')
s.select_city('DATI01573')
s.select_bank('600083')

# Let the tree load
time.sleep(2)

# 1. Check what the native ExtJS tree actually stores in the hidden field
# BEFORE we touch anything - read raw state
native_value = s.driver.execute_script("""
    var inputs = document.getElementsByName('ReportTree_CheckNodes');
    return inputs.length > 0 ? inputs[0].value : 'NOT FOUND';
""")
print("[BEFORE CHECK] ReportTree_CheckNodes raw value:", repr(native_value))

# 2. Now let ExtJS natively check the boxes via the UI click on checkbox DOM element
# This is what happens when a real user clicks a checkbox
print("Natively clicking checkboxes via DOM...")
s.driver.execute_script("""
    var t = Ext.getCmp('ReportTree');
    var seen = {};
    t.getRootNode().cascadeBy(function(node) {
        if (node.isLeaf()) {
            var text = node.get('text');
            if (!seen[text]) {
                // Use the NATIVE ExtJS check method - not fireEvent
                t.getView().onCheckChange(node, true);
                seen[text] = true;
            }
        }
    });
""")
time.sleep(1)

# 3. Now read hidden field AFTER native ExtJS check
after_value = s.driver.execute_script("""
    var inputs = document.getElementsByName('ReportTree_CheckNodes');
    return inputs.length > 0 ? inputs[0].value : 'NOT FOUND';
""")
print("[AFTER NATIVE CHECK] ReportTree_CheckNodes raw value:", repr(after_value))

# 4. Intercept the full POST body  
s.driver.execute_script("""
    window._postData = null;
    var origSend = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send = function(data) {
        window._postData = data;
        origSend.apply(this, arguments);
    };
""")

# 5. Click the button
print("Clicking Tampilkan button...")
s.driver.execute_script("""
    var btn = Ext.getCmp('ShowReportButton');
    if (btn) btn.getEl().dom.click();
""")

time.sleep(3)

post_data = s.driver.execute_script('return window._postData;')
print("\n[POST DATA sent to server (first 800 chars)]:")
print(str(post_data)[:800])

# Parse CheckNodes from POST
import urllib.parse
if post_data:
    params = urllib.parse.parse_qs(post_data)
    check_nodes = params.get('ReportTree_CheckNodes', ['NOT FOUND'])[0]
    print("\n[EXTRACTED ReportTree_CheckNodes]:", repr(check_nodes))

s.driver.quit()
