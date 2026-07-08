import sqlite3

conn = sqlite3.connect("jobs.db")
cursor = conn.cursor()

# Get all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
print("Tables:", tables)

for table in tables:
    tname = table[0]
    print(f"\n--- Table {tname} ---")
    try:
        cursor.execute(f"PRAGMA table_info({tname});")
        columns = cursor.fetchall()
        print("Columns:", [c[1] for c in columns])
        
        cursor.execute(f"SELECT * FROM {tname} LIMIT 10;")
        rows = cursor.fetchall()
        for r in rows:
            print(r)
    except Exception as e:
        print("Error:", e)

conn.close()
