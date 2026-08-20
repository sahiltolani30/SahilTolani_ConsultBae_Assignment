"""
Migration: adds skill_category column to candidates table.
Run ONCE before starting the n8n workflow.

Usage:
  cd SahilTolani_ConsultBae_Assignment
  python3 n8n_api/migrate_add_tag_column.py
"""
import sqlite3
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", os.path.join(_HERE, "..", "db", "consultbae.db"))


def migrate(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        # Check if column already exists (safe to re-run)
        cols = [row[1] for row in conn.execute("PRAGMA table_info(candidates)").fetchall()]
        if "skill_category" not in cols:
            conn.execute("ALTER TABLE candidates ADD COLUMN skill_category TEXT")
            conn.commit()
            print(f"✅  Added skill_category column to candidates ({db_path})")
        else:
            print(f"ℹ️   skill_category column already exists — nothing to do.")
    finally:
        conn.close()


if __name__ == "__main__":
    migrate(DB_PATH)
