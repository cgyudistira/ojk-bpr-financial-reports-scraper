import time, json
from src.scraper import OJKScraper
from src.database import Database
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

db = Database()
db.connect()
s = OJKScraper(db, headless=True)
s.setup_browser()

print("Opening page...")
s.open_page()
s.set_period("Desember", "2024")
s.select_province("DATI01126") # Bali
s.select_city("DATI01573")     # Denpasar
s.select_bank("600083")        # The first bank in Denpasar

print("Wait for tree to load...")
time.sleep(3)

# Expand tree nodes if not expanded
print("Expanding tree nodes via Selenium...")
try:
    # First, let's just use JS to expand the tree visually so Selenium can click checkboxes
    s._js("Ext.getCmp('ReportTree').expandAll();")
    time.sleep(2)
    
    # Now find all checkbox elements inside the tree and click them via Selenium
    checkboxes = s.driver.find_elements(By.CSS_SELECTOR, ".x-tree-checkbox")
    print(f"Found {len(checkboxes)} checkboxes.")
    
    clicked = 0
    for cb in checkboxes:
        try:
            # Check if it's already checked 
            if "x-tree-checkbox-checked" not in cb.get_attribute("class"):
                s.driver.execute_script("arguments[0].scrollIntoView(true);", cb)
                time.sleep(0.5)
                cb.click()
                clicked += 1
                time.sleep(0.5)
        except Exception as e:
            print(f"Error clicking cb: {e}")
            
    print(f"Clicked {clicked} checkboxes.")
    s.driver.save_screenshot("output/debug_selenium_checkboxes.png")
    
except Exception as e:
    print(f"Error checking boxes: {e}")

# Now try Selenium click on Tampilkan
print("Clicking Tampilkan via Selenium...")
try:
    btn = s.driver.find_element(By.ID, "ShowReportButton-btnEl")
    s.driver.execute_script("arguments[0].scrollIntoView(true);", btn)
    time.sleep(1)
    btn.click()
    print("Selenium click on Tampilkan done.")
except Exception as e:
    print(f"Error clicking Tampilkan: {e}")

print("Waiting for report...")
for i in range(5):
    time.sleep(5)
    info = s._js("""
        var area = document.getElementById('ReportViewerArea');
        if (!area) return 'no_area';
        var iframes = area.getElementsByTagName('iframe');
        return 'len=' + area.innerHTML.length + ' iframes=' + iframes.length;
    """)
    print(f"+{(i+1)*5}s: {info}")

s.driver.save_screenshot("output/debug_selenium_result.png")
s.close()
db.close()
