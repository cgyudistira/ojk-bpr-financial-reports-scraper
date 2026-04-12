"""
Debug: Check what value is submitted for ProvinceCode/CityCode hidden fields.
The server expects DATI codes but gets display text ("Provinsi Bali").
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

# Check ExtJS component values
info = s.driver.execute_script("""
    var prov = Ext.getCmp('ProvinceCode');
    var city = Ext.getCmp('CityCode');
    var bank = Ext.getCmp('BankCode');
    return {
        prov_value: prov ? prov.getValue() : 'N/A',
        prov_raw: prov ? prov.getRawValue() : 'N/A',
        prov_hiddenName: prov ? prov.hiddenName : 'N/A',
        prov_name: prov ? prov.name : 'N/A',
        city_value: city ? city.getValue() : 'N/A',
        city_raw: city ? city.getRawValue() : 'N/A',
        city_hiddenName: city ? city.hiddenName : 'N/A',
        city_name: city ? city.name : 'N/A',
        bank_value: bank ? bank.getValue() : 'N/A',
        bank_raw: bank ? bank.getRawValue() : 'N/A',
    };
""")
print("=== ExtJS Component Values ===")
for k, v in info.items():
    print(f"  {k}: {v}")

# Check hidden input elements
hiddens = s.driver.execute_script("""
    var results = [];
    var inputs = document.querySelectorAll('input[type=hidden]');
    for (var i = 0; i < inputs.length; i++) {
        var name = inputs[i].name;
        if (name && (name.indexOf('Province') > -1 || name.indexOf('City') > -1 || name.indexOf('Bank') > -1 || name.indexOf('Month') > -1 || name.indexOf('Year') > -1)) {
            results.push({name: name, value: inputs[i].value, id: inputs[i].id});
        }
    }
    return results;
""")
print("\n=== Hidden Input Fields ===")
for h in hiddens:
    print(f"  name={h['name']}, value={h['value']}, id={h['id']}")

s.driver.quit()
