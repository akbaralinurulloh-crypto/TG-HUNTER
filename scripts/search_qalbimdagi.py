import sqlite3

con = sqlite3.connect("data/hunter.db")
cur = con.cursor()

for r in cur.execute("SELECT id, state, posted_ids, caption, text FROM source_units WHERE caption LIKE '%Qalbimdagi%' OR text LIKE '%Qalbimdagi%'"):
    print(r)
