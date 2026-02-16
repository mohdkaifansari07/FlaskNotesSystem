import sqlite3

with open('schema.sql') as f:
    schema = f.read()

conn = sqlite3.connect('notes.db')
conn.executescript(schema)

conn.commit()
conn.close()

print("✅ SQLite database initialized successfully!")
