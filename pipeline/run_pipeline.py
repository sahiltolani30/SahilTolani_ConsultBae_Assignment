import os
import time
from pathlib import Path

from pipeline.database import init_db, insert_candidates, insert_candidate_skills
from pipeline.ingest import load_and_repair_source1, load_and_repair_source2, load_and_repair_source3
from pipeline.normalize import (
    normalize_phone, normalize_email, normalize_city, normalize_ctc, 
    normalize_rate, normalize_verified, normalize_date, normalize_skills, normalize_status
)
from pipeline.resolve import resolve_entities
from pipeline.merge import create_golden_record

def normalize_row(row, source_tag) -> dict:
    """Takes a raw pandas row dict, applies normalization, returns a cleaned dict."""
    rec = {'_source': source_tag}
    
    # Common helper to get first available key
    def get_val(*keys):
        for k in keys:
            if k in row and row[k] is not None and str(row[k]).strip():
                return row[k]
        return None

    # Full Name
    rec['full_name'] = str(get_val('Full Name', 'worker_name', 'Name')).strip()
    
    # Email
    rec['email'] = normalize_email(get_val('Email', 'email_id'))
    
    # Phone
    rec['phone'] = normalize_phone(get_val('Phone', 'Phone Number'))
    
    # City
    rec['city'] = normalize_city(get_val('City', 'location'))
    
    # Experience
    exp = get_val('Experience')
    if exp is not None:
        try:
            rec['experience_years'] = float(exp)
        except:
            rec['experience_years'] = None
            
    # CTC
    rec['ctc_inr'] = normalize_ctc(get_val('CTC'))
    
    # Hourly Rate
    rec['hourly_rate_inr'] = normalize_rate(get_val('rate'))
    
    # Skills
    rec['skills'] = normalize_skills(get_val('Skills', 'skill_tags'))
    
    # Verified
    rec['is_verified'] = normalize_verified(get_val('Verified'))
    
    # Projects
    proj = get_val('Projects Completed')
    if proj is not None:
        try:
            rec['projects_completed'] = int(proj)
        except:
            rec['projects_completed'] = None
            
    # Applied Date
    rec['applied_date'] = normalize_date(get_val('Applied Date'))
    
    # Gig Status
    rec['gig_status'] = normalize_status(get_val('status'))
    
    return rec

def run(data_dir: str, db_path: str, report_path: str, schema_path: str):
    print("--- ConsultBae Data Pipeline ---")
    start_time = time.time()
    
    all_issues = []
    
    # 1. Ingest & Structural Repair
    print("Phase 1: Ingesting data & repairing structure...")
    df1, iss1 = load_and_repair_source1(os.path.join(data_dir, 'source1_naukri_applicants.csv'))
    df2, iss2 = load_and_repair_source2(os.path.join(data_dir, 'source2_gig_workers.csv'))
    df3, iss3 = load_and_repair_source3(os.path.join(data_dir, 'source3_cbnexus_contacts.csv'))
    all_issues.extend(iss1 + iss2 + iss3)
    
    # 2. Normalize
    print("Phase 2: Normalizing fields...")
    all_records = []
    for _, row in df1.iterrows():
        all_records.append(normalize_row(row.to_dict(), 'src1'))
    for _, row in df2.iterrows():
        all_records.append(normalize_row(row.to_dict(), 'src2'))
    for _, row in df3.iterrows():
        all_records.append(normalize_row(row.to_dict(), 'src3'))
        
    print(f"Total valid raw records: {len(all_records)}")
        
    # 3. Entity Resolution
    print("Phase 3: Resolving entities (Union-Find clustering)...")
    clusters = resolve_entities(all_records)
    print(f"Identified {len(clusters)} unique individuals.")
    
    # 4. Golden Record Merge
    print("Phase 4: Creating Golden Records...")
    golden_records = [create_golden_record(cluster) for cluster in clusters]
    
    # 5. Database Insert
    print("Phase 5: Writing to SQLite database...")
    # Recreate DB for idempotency
    if os.path.exists(db_path):
        os.remove(db_path)
        
    conn = init_db(db_path, schema_path)
    
    record_map = insert_candidates(conn, golden_records)
    print(f"Inserted {len(golden_records)} distinct candidates into DB.")
    
    # Insert normalized skills
    skills_inserted = 0
    for rec in golden_records:
        cid = None
        if rec.get('email') in record_map:
            cid = record_map[rec['email']]
        elif rec.get('phone') in record_map:
            cid = record_map[rec['phone']]
            
        if cid and rec.get('skills'):
            skills_list = rec['skills'].split('|')
            insert_candidate_skills(conn, cid, skills_list)
            skills_inserted += len(skills_list)
            
    conn.close()
    print(f"Inserted {skills_inserted} skill mappings.")
    
    # Generate Audit Report (Task 4)
    print("Generating Data Issues Audit Report (Task 4)...")
    Path(report_path).parent.mkdir(parents=True, exist_ok=True)

    total_raw = len(all_records) + len(all_issues)
    merges = total_raw - len(clusters) - len(all_issues)
    elapsed = time.time() - start_time

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("# Task 4: Data Issues & Audit Report\n\n")
        f.write("> **Pipeline:** `SahilTolani_ConsultBae_Assignment/pipeline/`  \n")
        f.write("> **Run command:** `python3 -m pipeline.run_pipeline`  \n")
        f.write(f"> **Generated from:** 3 CSV sources, {total_raw} raw rows\n\n---\n\n")

        # Overview table
        f.write("## Overview\n\n")
        f.write("| Metric | Value |\n|---|---|\n")
        f.write(f"| Total raw rows across all sources | {total_raw} |\n")
        f.write(f"| Structural issues fixed/dropped | {len(all_issues)} |\n")
        f.write(f"| Semantic/normalization issue categories corrected | 9 |\n")
        f.write(f"| Duplicate records merged | {merges} |\n")
        f.write(f"| **Final unique golden records** | **{len(clusters)}** |\n")
        f.write(f"| Skill mappings in junction table | {skills_inserted} |\n")
        f.write(f"| Pipeline runtime | {elapsed:.3f}s |\n\n")
        f.write("> ⚡ **Idempotent:** Re-running the pipeline fully recreates `db/consultbae.db` from scratch. Safe to run multiple times.\n\n---\n\n")

        # Part 1: Structural
        f.write("## Part 1: Structural Issues (Pre-Normalization)\n\n")
        f.write("Detection method: Native Python `csv.reader` in `pipeline/ingest.py`.\n\n")
        structural_labels = [
            ("Issue 1 — Empty Row", "Source 2, Row 12", "Row was entirely blank", "Dropped silently; logged to audit report"),
            ("Issue 2 — Column Shift", "Source 2, Row 20", "skills_tags data landed in email_id column due to CSV export bug", "Detected via heuristic (commas but no `@`) and columns rotated left by 1"),
            ("Issue 3 — Repeated Header", "Source 3, Row 16", "Full header row injected mid-file", "Detected by comparing row values to header; dropped"),
        ]
        for label, source, problem, fix in structural_labels:
            f.write(f"### {label}\n")
            f.write(f"- **Source:** {source}\n")
            f.write(f"- **Problem:** {problem}\n")
            f.write(f"- **Fix:** {fix}\n\n")

        # Part 2: Semantic
        f.write("\n---\n\n## Part 2: Semantic Issues (Normalization — Phase 2)\n\n")
        f.write("All fixes are pure functions in `pipeline/normalize.py`.\n\n")
        semantic_issues = [
            ("Issue 4 — Inconsistent Phone Formats", "All 3", "normalize_phone()",
             "5 variants: `+91...`, `09...`, `919...`, `+91-...`, plain 10-digit.",
             "Strip all non-digits via `re.sub(r'\\D','',phone)`, take last 10 digits."),
            ("Issue 5 — Uppercase Emails", "Source 2", "normalize_email()",
             "e.g. `ISHA.CHOPRA95@MAILTEST.EXAMPLE.ORG` — breaks entity matching.",
             "`.strip().lower()` on every email."),
            ("Issue 6 — Email Alias Prefixes (`alt.`, `old.`, etc.)", "Source 1 Row 27", "normalize_email()",
             "`alt.nikhil.chopra70@example.com` is an alias for `nikhil.chopra70@example.com`.",
             "Strip common prefixes (`alt.`, `old.`, `work.`, etc.) before matching. Enables Union-Find to merge rows 27 & 37."),
            ("Issue 7 — Mixed CTC Format (LPA vs INR)", "Source 1", "normalize_ctc()",
             "~15 records use LPA floats (e.g. `4.2`) mixed with absolute INR (e.g. `417964`).",
             "Values < 200 → multiply by 100,000. Values >= 200 → keep as-is."),
            ("Issue 8 — Mixed Rate Format (/hr vs k/month)", "Source 2", "normalize_rate()",
             "~10 records use `k/month` (e.g. `15k/month`), rest use `/hr` (e.g. `1415/hr`).",
             "k/month: parse number × 1000 ÷ 160 hrs. /hr: parse number directly."),
            ("Issue 9 — Mixed Applied Date Formats", "Source 1", "normalize_date()",
             "6+ formats: `24-07-2026`, `2026-08-08`, `7 Jul 2026`, `07/13/2026`, `19 Jul 2026`.",
             "`dateutil.parser.parse()` → `.strftime('%Y-%m-%d')` → uniform ISO 8601."),
            ("Issue 10 — Inconsistent Verified Field", "Source 3", "normalize_verified()",
             "5 variants: `Y`, `yes`, `Yes`, `N`, `No`.",
             "Case-insensitive map: {y/yes/true/1} → 1, {n/no/false/0} → 0."),
            ("Issue 11 — Gig Status Casing", "Source 2", "normalize_status()",
             "Variants: `Active`, `active`, `ACTIVE`, `Inactive`, `paused`.",
             "`.lower()` → canonical Title Case. Required by DB CHECK constraint."),
            ("Issue 12 — City Synonyms & Casing", "All 3", "normalize_city()",
             "`GURGAON`→`Gurugram`, `Bengaluru`→`Bangalore`, trailing spaces, mixed case.",
             "Alias mapping dict + `.strip().lower()` + `.title()`."),
        ]
        for title, source, fn, problem, fix in semantic_issues:
            f.write(f"### {title}\n")
            f.write(f"- **Source:** {source} | **Function:** `{fn}`\n")
            f.write(f"- **Problem:** {problem}\n")
            f.write(f"- **Fix:** {fix}\n\n")

        # Part 2.5: DB Schema Design
        f.write("---\n\n## Part 3: Database Schema Design Rationale\n\n")
        f.write("Implemented in `db/schema.sql`. Key design decisions made for correctness and scale:\n\n")
        db_decisions = [
            ("WAL Mode (`PRAGMA journal_mode=WAL`)", "Allows concurrent readers (Flask + n8n) while a writer is active. Default SQLite journal mode blocks all reads during a write."),
            ("Foreign Key Enforcement (`PRAGMA foreign_keys=ON`)", "SQLite defaults to OFF for historical compatibility. Enabled explicitly so `audio_submissions → candidates` integrity is guaranteed."),
            ("UNIQUE on `email` and `phone`", "DB-level guard against any duplicate inserts that slip past application logic. Raises `IntegrityError` which we catch and log gracefully."),
            ("CHECK constraints on numeric fields", "e.g. `experience_years >= 0`, `is_verified IN (0, 1, NULL)`. Prevents garbage data at the storage layer."),
            ("`candidate_skills` junction table", "Skills are stored both pipe-separated in `candidates.skills` (for simple display) AND in a normalized 1-to-many junction table. Enables Task 2 n8n skill-category queries via indexed `skill` column."),
            ("INTEGER AUTOINCREMENT primary key", "SQLite-native, human-readable, simpler FK references vs UUID. Appropriate for assignment scale."),
        ]
        f.write("| Decision | Rationale |\n|---|---|\n")
        for decision, rationale in db_decisions:
            f.write(f"| **{decision}** | {rationale} |\n")

        # Part 4: Entity Resolution
        f.write("\n---\n\n## Part 4: Duplicate & Entity Resolution\n\n")
        f.write("Detection: Union-Find in `pipeline/resolve.py` — merge on identical normalized email OR phone.\n\n")
        f.write(f"**Result:** {total_raw - len(all_issues)} valid raw records → **{len(clusters)} unique golden records** ({merges} merges performed).\n\n")
        
        f.write("### Multi-Key Safety Net (The Union-Find Advantage)\n")
        f.write("If an unknown prefix (like `bizarre.rohit@x.com`) slips through because it wasn't in our prefixes list, our pipeline will still successfully catch and merge them!\n\n")
        f.write("Because we match on Email **OR** Phone Number, the resolution doesn't rely on email alone. Here is what happens:\n\n")
        f.write("- **Record A (Source 1):** `rohit@x.com` | Phone: `9999999999`\n")
        f.write("- **Record B (Source 2):** `bizarre.rohit@x.com` | Phone: `9999999999`\n\n")
        f.write("Even though the email normalizer missed the `bizarre.` prefix, the algorithm will see that both records share the exact same normalized phone number.\n\n")
        f.write("The Union-Find logic will cluster them together into the same person. Then, during the Merge Phase (Phase 4), our conflict resolution rules state that the email from Source 1 takes priority, so the final Golden Record will cleanly discard `bizarre.rohit@x.com` and keep `rohit@x.com`.\n\n")

        # Part 5: Conflict Resolution
        f.write("---\n\n## Part 5: Conflict Resolution Rules\n\n")
        f.write("Implemented in `pipeline/merge.py`:\n\n")
        rules = [
            ("full_name", "Longest name string wins"),
            ("email", "Priority: src1 → src2 → src3"),
            ("phone", "Priority: src1 → src3 → src2"),
            ("city", "Priority: src1 → src3 → src2"),
            ("experience_years", "Max across all sources"),
            ("ctc_inr", "src1 only"),
            ("hourly_rate_inr", "src2 only"),
            ("is_verified", "src3 only"),
            ("projects_completed", "src3 only; max if conflict"),
            ("applied_date", "src1 only"),
            ("gig_status", "src2 only"),
            ("skills", "UNION of all sources, deduplicated"),
            ("sources", "Comma-joined set: e.g. `src1,src2,src3`"),
        ]
        f.write("| Field | Rule |\n|---|---|\n")
        for field, rule in rules:
            f.write(f"| `{field}` | {rule} |\n")

        f.write(f"\n---\n\n## Summary\n\n")
        f.write(f"Pipeline ran to completion in `{elapsed:.3f}s`. **{len(clusters)} unique golden records** written to `db/consultbae.db`.\n\n")
        f.write(f"**Skill mappings:** {skills_inserted} rows inserted into `candidate_skills` junction table — ready for Task 2 n8n skill-category workflows.\n\n")
        f.write("> 📄 **Task 5 (Scale Analysis):** See `reports/scale_analysis.md` for a full breakdown of what breaks at 5,000+ users and the production migration path (Postgres + S3 + pgBouncer).\n")
        
    elapsed = time.time() - start_time
    print(f"Pipeline complete in {elapsed:.2f} seconds!")
    print(f"Output DB: {db_path}")
    print(f"Audit Report: {report_path}")

if __name__ == "__main__":
    run(
        data_dir="data",
        db_path="db/consultbae.db",
        report_path="reports/data_issues_report.md",
        schema_path="db/schema.sql"
    )
