import sqlite3

con = sqlite3.connect("data/hunter.db")
cur = con.cursor()

for r in cur.execute("SELECT id, state, posted_ids, substr(caption, 1, 60), created_at FROM source_units ORDER BY id DESC LIMIT 20"):
    print(r)
