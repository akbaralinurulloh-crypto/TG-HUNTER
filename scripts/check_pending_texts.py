import sqlite3

con = sqlite3.connect("data/hunter.db")
cur = con.cursor()

print("--- PENDING UNITS WITH TEXT ---")
for r in cur.execute("SELECT id, state, channel_id, substr(text, 1, 80) FROM source_units WHERE state IN ('received', 'processing') AND text != ''"):
    print(r)
