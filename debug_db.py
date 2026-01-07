import sqlite3
import sys

db_path = "example/PIONEER/rekordbox/exportLibrary.db"

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # List tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print("Tables:", tables)
    
    # Search for flac
    found = False
    for table in tables:
        table_name = table[0]
        print(f"Checking table: {table_name}")
        try:
            cursor.execute(f"SELECT * FROM {table_name}")
            rows = cursor.fetchmany(5)
            for row in rows:
                if "flac" in str(row).lower():
                    print(f"FOUND flac in {table_name}: {row}")
                    found = True
        except Exception as e:
            print(f"Error reading {table_name}: {e}")

    conn.close()
except Exception as e:
    print(f"Error: {e}")
