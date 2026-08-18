# Task 4: Data Issues & Audit Report

> **Pipeline:** `SahilTolani_ConsultBae_Assignment/pipeline/`  
> **Run command:** `python3 -m pipeline.run_pipeline`  
> **Generated from:** 3 CSV sources, 106 raw rows

---

## Overview

| Metric | Value |
|---|---|
| Total raw rows across all sources | 106 |
| Structural issues fixed/dropped | 3 |
| Semantic/normalization issue categories corrected | 9 |
| Duplicate records merged | 43 |
| **Final unique golden records** | **60** |
| Skill mappings in junction table | 257 |
| Pipeline runtime | 0.016s |

> ⚡ **Idempotent:** Re-running the pipeline fully recreates `db/consultbae.db` from scratch. Safe to run multiple times.

---

## Part 1: Structural Issues (Pre-Normalization)

Detection method: Native Python `csv.reader` in `pipeline/ingest.py`.

### Issue 1 — Empty Row
- **Source:** Source 2, Row 12
- **Problem:** Row was entirely blank
- **Fix:** Dropped silently; logged to audit report

### Issue 2 — Column Shift
- **Source:** Source 2, Row 20
- **Problem:** skills_tags data landed in email_id column due to CSV export bug
- **Fix:** Detected via heuristic (commas but no `@`) and columns rotated left by 1

### Issue 3 — Repeated Header
- **Source:** Source 3, Row 16
- **Problem:** Full header row injected mid-file
- **Fix:** Detected by comparing row values to header; dropped


---

## Part 2: Semantic Issues (Normalization — Phase 2)

All fixes are pure functions in `pipeline/normalize.py`.

### Issue 4 — Inconsistent Phone Formats
- **Source:** All 3 | **Function:** `normalize_phone()`
- **Problem:** 5 variants: `+91...`, `09...`, `919...`, `+91-...`, plain 10-digit.
- **Fix:** Strip all non-digits via `re.sub(r'\D','',phone)`, take last 10 digits.

### Issue 5 — Uppercase Emails
- **Source:** Source 2 | **Function:** `normalize_email()`
- **Problem:** e.g. `ISHA.CHOPRA95@MAILTEST.EXAMPLE.ORG` — breaks entity matching.
- **Fix:** `.strip().lower()` on every email.

### Issue 6 — Email Alias Prefixes (`alt.`, `old.`, etc.)
- **Source:** Source 1 Row 27 | **Function:** `normalize_email()`
- **Problem:** `alt.nikhil.chopra70@example.com` is an alias for `nikhil.chopra70@example.com`.
- **Fix:** Strip common prefixes (`alt.`, `old.`, `work.`, etc.) before matching. Enables Union-Find to merge rows 27 & 37.

### Issue 7 — Mixed CTC Format (LPA vs INR)
- **Source:** Source 1 | **Function:** `normalize_ctc()`
- **Problem:** ~15 records use LPA floats (e.g. `4.2`) mixed with absolute INR (e.g. `417964`).
- **Fix:** Values < 200 → multiply by 100,000. Values >= 200 → keep as-is.

### Issue 8 — Mixed Rate Format (/hr vs k/month)
- **Source:** Source 2 | **Function:** `normalize_rate()`
- **Problem:** ~10 records use `k/month` (e.g. `15k/month`), rest use `/hr` (e.g. `1415/hr`).
- **Fix:** k/month: parse number × 1000 ÷ 160 hrs. /hr: parse number directly.

### Issue 9 — Mixed Applied Date Formats
- **Source:** Source 1 | **Function:** `normalize_date()`
- **Problem:** 6+ formats: `24-07-2026`, `2026-08-08`, `7 Jul 2026`, `07/13/2026`, `19 Jul 2026`.
- **Fix:** `dateutil.parser.parse()` → `.strftime('%Y-%m-%d')` → uniform ISO 8601.

### Issue 10 — Inconsistent Verified Field
- **Source:** Source 3 | **Function:** `normalize_verified()`
- **Problem:** 5 variants: `Y`, `yes`, `Yes`, `N`, `No`.
- **Fix:** Case-insensitive map: {y/yes/true/1} → 1, {n/no/false/0} → 0.

### Issue 11 — Gig Status Casing
- **Source:** Source 2 | **Function:** `normalize_status()`
- **Problem:** Variants: `Active`, `active`, `ACTIVE`, `Inactive`, `paused`.
- **Fix:** `.lower()` → canonical Title Case. Required by DB CHECK constraint.

### Issue 12 — City Synonyms & Casing
- **Source:** All 3 | **Function:** `normalize_city()`
- **Problem:** `GURGAON`→`Gurugram`, `Bengaluru`→`Bangalore`, trailing spaces, mixed case.
- **Fix:** Alias mapping dict + `.strip().lower()` + `.title()`.

---

## Part 3: Database Schema Design Rationale

Implemented in `db/schema.sql`. Key design decisions made for correctness and scale:

| Decision | Rationale |
|---|---|
| **WAL Mode (`PRAGMA journal_mode=WAL`)** | Allows concurrent readers (Flask + n8n) while a writer is active. Default SQLite journal mode blocks all reads during a write. |
| **Foreign Key Enforcement (`PRAGMA foreign_keys=ON`)** | SQLite defaults to OFF for historical compatibility. Enabled explicitly so `audio_submissions → candidates` integrity is guaranteed. |
| **UNIQUE on `email` and `phone`** | DB-level guard against any duplicate inserts that slip past application logic. Raises `IntegrityError` which we catch and log gracefully. |
| **CHECK constraints on numeric fields** | e.g. `experience_years >= 0`, `is_verified IN (0, 1, NULL)`. Prevents garbage data at the storage layer. |
| **`candidate_skills` junction table** | Skills are stored both pipe-separated in `candidates.skills` (for simple display) AND in a normalized 1-to-many junction table. Enables Task 2 n8n skill-category queries via indexed `skill` column. |
| **INTEGER AUTOINCREMENT primary key** | SQLite-native, human-readable, simpler FK references vs UUID. Appropriate for assignment scale. |

---

## Part 4: Duplicate & Entity Resolution

Detection: Union-Find in `pipeline/resolve.py` — merge on identical normalized email OR phone.

**Result:** 103 valid raw records → **60 unique golden records** (43 merges performed).

### Multi-Key Safety Net (The Union-Find Advantage)
If an unknown prefix (like `bizarre.rohit@x.com`) slips through because it wasn't in our prefixes list, our pipeline will still successfully catch and merge them!

Because we match on Email **OR** Phone Number, the resolution doesn't rely on email alone. Here is what happens:

- **Record A (Source 1):** `rohit@x.com` | Phone: `9999999999`
- **Record B (Source 2):** `bizarre.rohit@x.com` | Phone: `9999999999`

Even though the email normalizer missed the `bizarre.` prefix, the algorithm will see that both records share the exact same normalized phone number.

The Union-Find logic will cluster them together into the same person. Then, during the Merge Phase (Phase 4), our conflict resolution rules state that the email from Source 1 takes priority, so the final Golden Record will cleanly discard `bizarre.rohit@x.com` and keep `rohit@x.com`.

---

## Part 5: Conflict Resolution Rules

Implemented in `pipeline/merge.py`:

| Field | Rule |
|---|---|
| `full_name` | Longest name string wins |
| `email` | Priority: src1 → src2 → src3 |
| `phone` | Priority: src1 → src3 → src2 |
| `city` | Priority: src1 → src3 → src2 |
| `experience_years` | Max across all sources |
| `ctc_inr` | src1 only |
| `hourly_rate_inr` | src2 only |
| `is_verified` | src3 only |
| `projects_completed` | src3 only; max if conflict |
| `applied_date` | src1 only |
| `gig_status` | src2 only |
| `skills` | UNION of all sources, deduplicated |
| `sources` | Comma-joined set: e.g. `src1,src2,src3` |

---

## Summary

Pipeline ran to completion in `0.016s`. **60 unique golden records** written to `db/consultbae.db`.

**Skill mappings:** 257 rows inserted into `candidate_skills` junction table — ready for Task 2 n8n skill-category workflows.

> 📄 **Task 5 (Scale Analysis):** See `reports/scale_analysis.md` for a full breakdown of what breaks at 5,000+ users and the production migration path (Postgres + S3 + pgBouncer).
