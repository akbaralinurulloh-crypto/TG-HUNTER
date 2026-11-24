import sqlite3

con = sqlite3.connect("data/hunter.db")
cur = con.cursor()
cur.execute("UPDATE source_units SET state = 'received', decision_reason = NULL, decision_detail = NULL WHERE state IN ('error', 'dryrun')")
con.commit()
print("Updated rows:", cur.rowcount)
