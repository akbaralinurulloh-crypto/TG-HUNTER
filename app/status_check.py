import sqlite3

con = sqlite3.connect("data/hunter.db")
cur = con.cursor()

print("--- Source units summary ---")
for row in cur.execute("SELECT state, count(*) FROM source_units GROUP BY state"):
    print(f"State {row[0]}: {row[1]}")

print("\n--- Recent units ---")
for row in cur.execute("SELECT id, state, channel_id, decision_reason, substr(caption, 1, 50) FROM source_units ORDER BY id DESC LIMIT 10"):
    print(row)
