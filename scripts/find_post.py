import sqlite3

con = sqlite3.connect("data/hunter.db")
cur = con.cursor()

print("--- POSTED UNITS ---")
for r in cur.execute("SELECT id, channel_id, text, caption, posted_ids FROM source_units WHERE state = 'posted'"):
    print(f"ID: {r[0]}")
    print(f"Text: {r[2]}")
    print(f"Caption: {r[3]}")
    print(f"Posted IDs: {r[4]}")
    print("-" * 30)

print("\n--- ALL UNITS WITH AVTOBUS/YIG'ILISH/GURUH HABARLARI ---")
for r in cur.execute("SELECT id, state, text, caption FROM source_units WHERE text != ''"):
    low = (r[2] + " " + (r[3] or "")).lower()
    if any(k in low for k in ["avtobus", "yig'il", "yigil", "chiqilar", "chiqinglar", "bormoqchilar", "soat"]):
        print(f"ID {r[0]} ({r[1]}): {r[2][:100]}")
