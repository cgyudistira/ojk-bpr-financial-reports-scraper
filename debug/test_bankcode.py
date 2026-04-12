"""Check what BankCode value gets set and what the tree node texts look like."""
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

val = s.driver.execute_script("""
    var cmp = Ext.getCmp("BankCode");
    var inputVal = document.querySelector("input[name='BankCode']");
    return {
        cmpValue: cmp ? cmp.getValue() : "N/A",
        inputValue: inputVal ? inputVal.value : "N/A"
    };
""")
print("BankCode state:", val)

tree_text = s.driver.execute_script("""
    var bc = Ext.getCmp("BankCode");
    if (!bc) return "no cmp";
    var tree = bc.component;
    if (!tree) return "no tree";
    var root = tree.getRootNode();
    if (!root || !root.childNodes.length) return "no children";
    var texts = [];
    root.cascadeBy(function(n) {
        if (n.isLeaf()) texts.push(n.get("text"));
    });
    return texts;
""")
print("Bank tree texts:", tree_text)

s.driver.quit()
