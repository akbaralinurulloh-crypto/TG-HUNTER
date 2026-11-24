import sqlite3

con = sqlite3.connect("data/hunter.db")
cur = con.cursor()

for r in cur.execute("SELECT id, posted_ids, caption FROM source_units WHERE state = 'posted' ORDER BY id DESC LIMIT 5"):
    print("ID:", r[0])
    print("Posted IDs:", r[1])
    print("Caption:", r[2])
    print("-" * 30)
