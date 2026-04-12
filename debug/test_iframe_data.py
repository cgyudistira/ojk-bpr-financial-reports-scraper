"""
Final verification: Wait for iframes to load and check if tables contain data.
"""
from src.scraper import OJKScraper
from src.database import Database
import time

db = Database()
db.connect()

row = db.conn.execute("SELECT nama FROM bank WHERE code = '600083'").fetchone()
bank_name = row[0] if row else ""
print(f"Bank: 600083-{bank_name}")

s = OJKScraper(db, headless=True)
s.setup_browser()
s.open_page()
s.set_period('Desember', '2024')
s.select_province('DATI01126')
s.select_city('DATI01573')
s.select_bank('600083', bank_name)
s.check_all_reports()
result = s.click_tampilkan()
print(f"click_tampilkan: {result}")

if result:
    # Wait extra time for iframes to load their SSRS content
    time.sleep(10)
    
    iframe_data = s.driver.execute_script("""
        var area = document.getElementById('ReportViewerArea');
        if (!area) return [];
        var iframes = area.getElementsByTagName('iframe');
        var results = [];
        for (var i = 0; i < iframes.length; i++) {
            try {
                var doc = iframes[i].contentDocument || iframes[i].contentWindow.document;
                var tables = doc.getElementsByTagName('table');
                var text = doc.body ? doc.body.innerText.substring(0, 300) : '';
                results.push({
                    idx: i,
                    src: iframes[i].src.substring(0, 100),
                    tables: tables.length,
                    bodyLen: doc.body ? doc.body.innerHTML.length : 0,
                    text: text
                });
            } catch(e) {
                results.push({idx: i, error: e.message});
            }
        }
        return results;
    """)
    
    for item in iframe_data:
        print(f"\n--- Iframe {item.get('idx', '?')} ---")
        if 'error' in item:
            print(f"  Cross-origin error: {item['error']}")
        else:
            print(f"  src: {item.get('src', 'N/A')}")
            print(f"  tables: {item.get('tables', 0)}")
            print(f"  bodyLen: {item.get('bodyLen', 0)}")
            text_preview = item.get('text', '')[:200]
            if text_preview:
                print(f"  text: {text_preview}")

s.driver.save_screenshot('debug/test_iframes_loaded.png')
print("\nScreenshot saved.")
s.driver.quit()
db.close()
