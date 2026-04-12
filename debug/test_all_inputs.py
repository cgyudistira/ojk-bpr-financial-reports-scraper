"""
Debug: Check ALL form inputs (not just hidden) to find any missing state fields.
Focus on finding what ShowReportButton_DirectClick uses at offset +303.
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

# Dump ALL input elements
all_inputs = s.driver.execute_script("""
    var results = [];
    var all = document.querySelectorAll('input, textarea, select');
    for (var i = 0; i < all.length; i++) {
        var el = all[i];
        results.push({
            tag: el.tagName,
            type: el.type || '',
            name: el.name || '',
            id: el.id || '',
            value: (el.value || '').substring(0, 100)
        });
    }
    return results;
""")

print(f"=== ALL {len(all_inputs)} FORM ELEMENTS ===")
for inp in all_inputs:
    if inp['name'] or inp['id']:
        print(f"  <{inp['tag']} type={inp['type']} name='{inp['name']}' id='{inp['id']}'> = '{inp['value']}'")

# Also check if BankCode has a special value format
bank_info = s.driver.execute_script("""
    var cmp = Ext.getCmp('BankCode');
    if (!cmp) return 'no cmp';
    return {
        value: cmp.getValue(),
        raw: cmp.getRawValue ? cmp.getRawValue() : 'N/A',
        name: cmp.name,
        hiddenName: cmp.hiddenName || 'none',
        inputId: cmp.inputEl ? cmp.inputEl.dom.id : 'N/A',
        inputVal: cmp.inputEl ? cmp.inputEl.dom.value : 'N/A',
        xtype: cmp.xtype
    };
""")
print("\n=== BankCode Component ===")
print(bank_info)

s.driver.quit()
