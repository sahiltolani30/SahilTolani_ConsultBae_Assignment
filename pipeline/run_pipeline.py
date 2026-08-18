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
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("# Task 4: Data Issues & Audit Report\n\n")
        f.write("## Overview\n")
        f.write(f"- **Total raw rows processed**: {len(all_records) + len(all_issues)}\n")
        f.write(f"- **Total structural issues fixed/dropped**: {len(all_issues)}\n")
        f.write(f"- **Final unique golden records generated**: {len(clusters)}\n\n")
        
        f.write("## Structural Issues Found (Pre-Normalization)\n")
        for iss in all_issues:
            f.write(f"- {iss}\n")
            
        f.write("\n## Pipeline Architecture Recap\n")
        f.write("- **Phase 1**: Native Python `csv` parsing to catch shifted columns and repeated headers before Pandas crashes.\n")
        f.write("- **Phase 2**: Pure-function normalization (emails lowercased, phones to 10-digit, CTC Lakhs to INR).\n")
        f.write("- **Phase 3**: Transitive O(1) clustering using the `Union-Find` algorithm (matches by Phone OR Email).\n")
        f.write("- **Phase 4**: Strict conflict-resolution prioritization to generate a single Golden Record per person.\n")
        f.write("- **Phase 5**: SQLite WAL-mode bulk insert, with normalized skills stored in a junction table.\n")
        
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
