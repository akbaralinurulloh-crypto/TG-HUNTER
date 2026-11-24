import sqlite3

con = sqlite3.connect("data/hunter.db")
cur = con.cursor()

for r in cur.execute("SELECT id, state, text, caption, posted_ids FROM source_units WHERE text LIKE '%дастурхонда%'"):
    print(r)
