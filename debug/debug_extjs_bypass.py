import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

def main():
    options = Options()
    options.add_argument('--headless=new')
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    print("Opening page...")
    driver.get("https://cfs.ojk.go.id/cfs/Report.aspx?BankTypeCode=BPK&BankTypeName=BPR%20Konvensional")
    time.sleep(10)
    
    script0 = """
    var m = Ext.getCmp('Month');
    if(m) { m.setValue('Desember'); m.fireEvent('select', m); }
    var y = Ext.getCmp('Year');
    if(y) { y.setValue(2024); }
    """
    print("Setting Period (Triggering server bug)...")
    driver.execute_script(script0)
    time.sleep(5)

    script1 = """
    var p = Ext.getCmp('ProvinceCode');
    if(p) { p.setValue('DATI00101'); p.fireEvent('select', p); }
    """
    print("Selecting Province...")
    driver.execute_script(script1)
    time.sleep(5)
    
    script2 = """
    var c = Ext.getCmp('CityCode');
    if(c) { c.setValue('DATI00102'); c.fireEvent('select', c); }
    """
    print("Selecting City...")
    driver.execute_script(script2)
    time.sleep(5)
    
    script3 = """
    var bc = Ext.getCmp('BankCode');
    if(bc) {
        var store = Ext.getStore('BankTreeStore');
        var node = store.getNodeById('600007');
        if(node) {
            bc.setValue('600007');
            bc.setRawValue(node.get('text'));
            bc.fireEvent('select', bc);
            bc.fireEvent('change', bc, '600007');
        }
    }
    """
    print("Selecting Bank...")
    driver.execute_script(script3)
    time.sleep(5)
    
    # Bypass ExtJS ReportTree bug by directly setting the hidden input field
    script_bypass = """
    var inputs = document.getElementsByName('ReportTree_CheckNodes');
    if (inputs.length > 0) {
        // Set the report ID (must match exactly what ExtJS would put there)
        inputs[0].value = 'BPK-901-000001';
        return "Bypass successful: " + inputs[0].value;
    }
    return "Hidden input ReportTree_CheckNodes not found!";
    """
    print("Injecting Report ID directly to hidden field...")
    res = driver.execute_script(script_bypass)
    print(res)
    
    # Click ShowReportButton
    script_click = """
    var btn = Ext.getCmp('ShowReportButton');
    if (btn) {
        btn.fireEvent('click', btn);
        return "Clicked using ExtJS API";
    }
    var btnDom = document.getElementById('ShowReportButton');
    if (btnDom) {
        btnDom.click();
        return "Clicked using DOM";
    }
    return "Button not found";
    """
    print("Clicking Tampilkan...")
    res2 = driver.execute_script(script_click)
    print(res2)
    time.sleep(15)
    
    # Check if iframe loaded
    iframe_src = driver.execute_script("var f = document.querySelector('iframe'); return f ? f.src : 'No iframe';")
    print(f"Report iframe wrapper src: {iframe_src}")
    
    has_viewer = driver.execute_script("return !!document.getElementById('CFSReportViewer');")
    print(f"Report viewer component exists: {has_viewer}")

    driver.quit()

if __name__ == "__main__":
    main()
