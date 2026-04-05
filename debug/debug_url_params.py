import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

def test_url_params():
    print("Setting up Chrome...")
    options = Options()
    options.add_argument('--headless=new')
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    try:
        # Try both Month=9 and pMonth=9 (common SSRS param prefix)
        urls = [
            "https://cfs.ojk.go.id/cfs/Report.aspx?BankTypeCode=BPK&BankTypeName=BPR%20Konvensional&Month=9&Year=2025",
            "https://cfs.ojk.go.id/cfs/Report.aspx?BankTypeCode=BPK&BankTypeName=BPR%20Konvensional&pMonth=9&pYear=2025"
        ]
        
        for url in urls:
            print(f"Testing URL: {url}")
            driver.get(url)
            time.sleep(10)
            
            # Check what month is selected
            val = driver.execute_script("return Ext.getCmp('Month').getValue();")
            text = driver.execute_script("return Ext.getCmp('Month').getRawValue();")
            yr = driver.execute_script("return Ext.getCmp('Year').getValue();")
            
            print(f"Selected Month: {val} ({text})")
            print(f"Selected Year: {yr}")
            if str(val) == "9" and str(yr) == "2025":
                print("SUCCESS! URL params work.")
                return

        print("URL params did NOT change the default period.")
    finally:
        driver.quit()

if __name__ == "__main__":
    test_url_params()
