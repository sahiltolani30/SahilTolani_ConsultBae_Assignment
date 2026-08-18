import sqlite3
import pathlib

def get_connection(db_path: str) -> sqlite3.Connection:
    """Get a SQLite connection with WAL mode and FK enforcement enabled."""
    # Using check_same_thread=False is generally safe if we manage connections properly,
    # but for this script we stick to default thread safety.
    conn = sqlite3.connect(db_path)
    # Enable WAL mode for concurrent read/write
    conn.execute("PRAGMA journal_mode=WAL;")
    # Enforce foreign keys (SQLite defaults to OFF for backwards compatibility)
    conn.execute("PRAGMA foreign_keys=ON;")
    # Return rows as dictionaries
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path: str, schema_path: str) -> sqlite3.Connection:
    """Create DB, run schema.sql, enable WAL + FK enforcement."""
    # Ensure directory exists
    pathlib.Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    
    conn = get_connection(db_path)
    
    with open(schema_path, 'r', encoding='utf-8') as f:
        schema_sql = f.read()
    
    # Executescript runs all statements in the SQL file
    conn.executescript(schema_sql)
    conn.commit()
    return conn

def insert_candidates(conn: sqlite3.Connection, records: list[dict]) -> dict:
    """
    Insert golden records into the candidates table.
    Returns a mapping of (email or phone) -> candidate_id to help insert skills later.
    """
    if not records:
        return {}

    # Extract all possible keys for the insert based on the schema
    keys = [
        'full_name', 'email', 'phone', 'city', 'experience_years',
        'ctc_inr', 'hourly_rate_inr', 'skills', 'is_verified',
        'projects_completed', 'applied_date', 'gig_status', 'sources'
    ]
    
    placeholders = ", ".join(["?"] * len(keys))
    columns = ", ".join(keys)
    sql = f"INSERT INTO candidates ({columns}) VALUES ({placeholders})"
    
    record_map = {} # email -> id, or phone -> id
    
    cursor = conn.cursor()
    for record in records:
        values = [record.get(k) for k in keys]
        try:
            cursor.execute(sql, values)
            candidate_id = cursor.lastrowid
            
            # Map by email and/or phone so we can reference it for skill insertion
            if record.get('email'):
                record_map[record['email']] = candidate_id
            if record.get('phone'):
                record_map[record['phone']] = candidate_id
        except sqlite3.IntegrityError as e:
            # Handle uniqueness violations gracefully
            print(f"Skipping insert for {record.get('email') or record.get('phone')}: {e}")
            
    conn.commit()
    return record_map

def insert_candidate_skills(conn: sqlite3.Connection, candidate_id: int, skills: list[str]):
    """Insert normalized skills into the candidate_skills junction table."""
    if not skills:
        return
        
    cursor = conn.cursor()
    sql = "INSERT OR IGNORE INTO candidate_skills (candidate_id, skill) VALUES (?, ?)"
    values = [(candidate_id, skill.strip()) for skill in skills if skill.strip()]
    
    cursor.executemany(sql, values)
    conn.commit()
