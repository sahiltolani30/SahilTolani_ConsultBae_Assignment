-- Enable WAL mode for concurrent read/write (Flask + n8n)
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- ═══════════════════════════════════════════
-- Table: candidates (Task 1 output, Tasks 2/3 reference)
-- ═══════════════════════════════════════════
CREATE TABLE IF NOT EXISTS candidates (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name           TEXT NOT NULL,
    email               TEXT UNIQUE,
    phone               TEXT UNIQUE,
    city                TEXT,
    experience_years    REAL CHECK (experience_years IS NULL OR experience_years >= 0),
    ctc_inr             REAL CHECK (ctc_inr IS NULL OR ctc_inr >= 0),
    hourly_rate_inr     REAL CHECK (hourly_rate_inr IS NULL OR hourly_rate_inr >= 0),
    skills              TEXT,               -- pipe-separated: "Python|Docker|n8n"
    is_verified         INTEGER CHECK (is_verified IN (0, 1, NULL)),
    projects_completed  INTEGER CHECK (projects_completed IS NULL OR projects_completed >= 0),
    applied_date        TEXT,               -- ISO 8601: YYYY-MM-DD
    gig_status          TEXT CHECK (gig_status IN ('Active', 'Inactive', 'Paused', NULL)),
    sources             TEXT NOT NULL,       -- "src1,src2,src3"
    created_at          TEXT DEFAULT (datetime('now'))
);

-- Indexes for fast lookups from n8n + Flask audio app
CREATE INDEX IF NOT EXISTS idx_candidates_city ON candidates(city);
CREATE INDEX IF NOT EXISTS idx_candidates_gig_status ON candidates(gig_status);

-- ═══════════════════════════════════════════
-- Table: candidate_skills (normalized, for Task 2 n8n queries)
-- ═══════════════════════════════════════════
CREATE TABLE IF NOT EXISTS candidate_skills (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id    INTEGER NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    skill           TEXT NOT NULL,
    UNIQUE(candidate_id, skill)
);

CREATE INDEX IF NOT EXISTS idx_skills_skill ON candidate_skills(skill);
CREATE INDEX IF NOT EXISTS idx_skills_candidate ON candidate_skills(candidate_id);

-- ═══════════════════════════════════════════
-- Table: audio_submissions (Task 3)
-- ═══════════════════════════════════════════
CREATE TABLE IF NOT EXISTS audio_submissions (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id            INTEGER REFERENCES candidates(id),
    name                    TEXT NOT NULL,
    phone                   TEXT NOT NULL,
    file_path               TEXT NOT NULL,
    duration_seconds        REAL,
    sample_rate_khz         REAL,
    bitrate_kbps            INTEGER,
    loudness_db             REAL,
    noise_quality_estimate  TEXT,
    submitted_at            TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_audio_candidate ON audio_submissions(candidate_id);
CREATE INDEX IF NOT EXISTS idx_audio_phone ON audio_submissions(phone);
