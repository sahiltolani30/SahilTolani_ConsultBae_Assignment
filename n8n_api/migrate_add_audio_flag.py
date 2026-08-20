import sqlite3, os

DB = os.path.join(os.path.dirname(__file__), '..', 'db', 'consultbae.db')
conn = sqlite3.connect(DB)
try:
    conn.execute("ALTER TABLE candidates ADD COLUMN audio_flagged INTEGER DEFAULT 0")
    conn.execute("ALTER TABLE candidates ADD COLUMN audio_flag_reason TEXT")
    conn.commit()
    print("✅ Added audio_flagged and audio_flag_reason to candidates")
except sqlite3.OperationalError as e:
    print(f"Already exists or error: {e}")
finally:
    conn.close()
