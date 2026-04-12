"""Check what the bank setValue format should be - the server expects 'code-name' format."""
from src.database import Database

db = Database()
rows = db.conn.execute(
    "SELECT code, nama FROM bank WHERE provinsi_code = ? AND kabupaten_code = ? LIMIT 5",
    ('DATI01126', 'DATI01573')
).fetchall()
for r in rows:
    print(f"code={r[0]}, nama={r[1]}")
    print(f"  → expected BankCode value: {r[0]}-{r[1]}")
db.close()
