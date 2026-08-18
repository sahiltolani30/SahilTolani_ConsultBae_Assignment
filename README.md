# Sahil Tolani — ConsultBae AI Automation Assignment

This repository contains the full end-to-end solution for the ConsultBae Take-Home Assignment.

## Setup Instructions

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the data pipeline:
   ```bash
   python -m pipeline.run_pipeline
   ```
   *This will process the raw data in `data/`, create the SQLite database at `db/consultbae.db`, and generate the Task 4 audit report.*

---

## 🛠️ Task 1: Data Engineering Pipeline

**Objective:** Ingest, clean, normalize, and merge 3 disparate CSV sources into a single "Golden Record" database table while mapping skills into a relational junction table for downstream tasks.

### How it was solved (The Pipeline Architecture):

Our pipeline (`pipeline/run_pipeline.py`) processes the data in 5 strict phases to ensure data integrity and traceability:

1. **Phase 1: Ingest & Repair (`ingest.py`)** 
   - Uses native Python `csv` reader to catch structural issues *before* they hit Pandas.
   - Automatically drops empty rows, drops injected headers, and realigns column-shifted rows (e.g., when skill data leaked into the email column in Source 2).
   
2. **Phase 2: Normalization (`normalize.py`)**
   - Applies pure, side-effect-free functions to normalize fields.
   - Cleans mixed phone formats, lowercases emails, strips alias prefixes (`alt.`, `old.`), converts LPA floats to absolute INR, standardizes mixed rate formats, and parses dates into ISO 8601 strings.
   
3. **Phase 3: Entity Resolution (`resolve.py`)**
   - Implements a **Union-Find (Disjoint Set)** algorithm to perform multi-key transitive clustering.
   - **Matching Logic:** If Record A and Record B share an email *OR* a 10-digit phone number, they are clustered as the same individual. This gracefully catches edge cases where an email has a weird prefix but the phone number matches.
   
4. **Phase 4: Golden Record Creation (`merge.py`)**
   - Flattens each cluster of records into a single Golden Record using strict conflict resolution rules (e.g., CTC always comes from Source 1, longest name string wins, Skills are UNIONed across all sources).
   
5. **Phase 5: Database Loading (`database.py`)**
   - Writes the 60 unique Golden Records to `db/consultbae.db` (SQLite).
   - Uses a normalized junction table (`candidate_skills`) to store the 257 distinct skill mappings, enabling the Task 2 n8n workflow to query candidates by skill category efficiently.
   - **Design Choices:** Uses `PRAGMA journal_mode=WAL` to allow concurrent readers (like n8n and Flask) while writing, and enforces constraints like `UNIQUE` emails/phones and `CHECK` rules on numeric fields.

*Note: Running the pipeline automatically generates the Task 4 Data Issues Audit Report in `reports/data_issues_report.md`.*
