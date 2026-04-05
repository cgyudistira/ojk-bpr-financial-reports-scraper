import sqlite3
import os

db_path = r"d:\Projects\vibe\OJK BPR\data\ojk_bpr.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM provinsi;")
    p_count = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM kabupaten;")
    k_count = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM bank;")
    b_count = cur.fetchone()[0]
    print(f"Stats - Provinsi: {p_count}, Kabupaten: {k_count}, Bank: {b_count}")
    conn.close()
else:
    print("Database not found")
