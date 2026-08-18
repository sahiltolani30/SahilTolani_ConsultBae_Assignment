# ConsultBae — AI Automation Take-Home Assignment
**Sahil Tolani** · sahiltolani30@gmail.com

---

## 1. Overview

This repository is the end-to-end solution for the ConsultBae AI Automation take-home assignment. It covers a data engineering pipeline that merges three messy CSV sources into a single database, a Flask-based audio collection web app with custom audio quality analysis, an n8n automation workflow, a full data quality audit, and a production scalability write-up.

---

## 2. Architecture

```
data/                        ← 3 raw CSV sources
   └── pipeline/             ← 5-phase data cleaning + merge pipeline
         └── db/consultbae.db ← SQLite golden record database
               ├── audio_app/ ← Flask audio recording web app
               └── n8n/       ← n8n workflow JSON export
reports/
   ├── data_issues_report.md  ← Task 4: every issue found, row by row
   └── scale_analysis.md      ← Task 5: what breaks at 5,000 users
```

The database is the shared backbone. The pipeline writes to it, the audio app reads/writes to it, and the n8n automation queries it.

---

## 3. Tech Stack

| Layer | Tool |
|---|---|
| Language | Python 3.9+ |
| Data Pipeline | Pandas, native `csv`, Union-Find |
| Database | SQLite (WAL mode) |
| Web Framework | Flask 3.0 |
| Audio Processing | pydub, static-ffmpeg, numpy (FFT) |
| Automation | n8n |
| Audio Recording (browser) | MediaRecorder API (WebM/Opus) |

---

## 4. Project Structure

```
SahilTolani_ConsultBae_Assignment/
├── data/
│   ├── source1_naukri_applicants.csv
│   ├── source2_gig_workers.csv
│   └── source3_cbnexus_contacts.csv
├── pipeline/
│   ├── run_pipeline.py       ← entry point
│   ├── ingest.py             ← Phase 1: load + structural repair
│   ├── normalize.py          ← Phase 2: clean all field formats
│   ├── resolve.py            ← Phase 3: Union-Find entity matching
│   ├── merge.py              ← Phase 4: golden record creation
│   └── database.py           ← Phase 5: write to SQLite
├── audio_app/
│   ├── app.py                ← Flask routes
│   ├── audio_processor.py    ← FFT-based noise quality detection
│   └── templates/
│       ├── index.html        ← record / upload page
│       └── submissions.html  ← all submissions view
├── db/
│   ├── schema.sql
│   └── consultbae.db
├── n8n/                      ← n8n workflow JSON export
├── reports/
│   ├── data_issues_report.md
│   └── scale_analysis.md
├── requirements.txt
└── README.md
```

---

## 5. Setup & Installation

### Requirements
- Python 3.9+
- pip
- No system-level ffmpeg needed (handled automatically by `static-ffmpeg`)

### Installation

```bash
git clone https://github.com/sahiltolani30/SahilTolani_ConsultBae_Assignment.git
cd SahilTolani_ConsultBae_Assignment
pip install -r requirements.txt
```

### Environment Variables

None required. The app runs fully local out of the box.

### Run the Data Pipeline

```bash
python3 -m pipeline.run_pipeline
```

This will:
- Process all 3 CSV sources
- Clean, normalize, and deduplicate 106 raw rows into 60 golden records
- Write the database to `db/consultbae.db`
- Auto-generate the Task 4 audit report at `reports/data_issues_report.md`

### Run the Audio Application

```bash
python3 -m flask --app audio_app/app.py run --port 5001
```

Then open **http://127.0.0.1:5001** in your browser.

> Note: Port 5000 is occupied by macOS AirPlay Receiver on Apple Silicon Macs. Use 5001.

---

## 6. Task 1 — Data Merge

### Objective
Ingest 3 CSVs from different talent platforms, clean them, and merge them into a single unified candidate database with no duplicates.

### Data Sources

| Source | Platform | Raw Rows | Issues |
|---|---|---|---|
| source1_naukri_applicants.csv | Naukri job board | 41 | CTC in mixed units, garbled rows |
| source2_gig_workers.csv | Gig platform | 36 | Hourly rates in mixed units, column shift bug, empty row |
| source3_cbnexus_contacts.csv | CBNexus internal | 29 | Repeated header row, alias email prefixes |

### Data Processing Pipeline

The pipeline runs in 5 strict phases:

**Phase 1 — Ingest & Structural Repair** (`ingest.py`)
Uses raw `csv.reader` before Pandas touches anything. Catches empty rows, injected duplicate headers, and column-shifted rows where skill data leaked into the email column.

**Phase 2 — Normalization** (`normalize.py`)
Field-by-field cleaning functions:
- Phones → 10-digit Indian mobile numbers (strips +91, 0 prefix, country codes)
- Emails → lowercase, strip whitespace, remove `alt.`/`old.` alias prefixes
- CTC → all converted to absolute INR (detects float-in-lakhs like `4.2` vs absolute int like `417964`)
- Hourly rates → all converted to INR/hour (detects `k/month` and `/hr` formats)
- Dates → ISO 8601 (YYYY-MM-DD)
- Verified field → boolean integer (handles Y/N/yes/no/Yes/1/0)
- City names → canonical mapping (e.g. `Bengaluru` / `Bangalore` → `Bengaluru`)

**Phase 3 — Entity Resolution** (`resolve.py`)
Uses a **Union-Find (Disjoint Set Union)** algorithm. Two records are clustered as the same person if they share a normalized email OR a normalized 10-digit phone. This handles transitive matches (A matches B by email, B matches C by phone → A, B, C are the same person).

**Phase 4 — Golden Record Merge** (`merge.py`)
Conflict resolution rules per field:
- `full_name`: longest string wins
- `ctc_inr`: Source 1 has priority (most complete salary data)
- `email`: non-alias email preferred
- `skills`: UNION of all skills across all sources
- `city`: majority vote, Source 1 tiebreaker

**Phase 5 — Database Write** (`database.py`)
Writes using `INSERT OR REPLACE` under a single transaction. Skills written to a normalized `candidate_skills` junction table for efficient querying.

### Database Schema

3 tables:
- `candidates` — 60 golden records
- `candidate_skills` — 257 skill mappings (junction table)
- `audio_submissions` — Task 3 audio submissions

### Results

| Metric | Value |
|---|---|
| Raw rows across all sources | 106 |
| Structural issues fixed | 3 |
| Normalization issue categories | 9 |
| Duplicate clusters merged | 43 |
| **Final golden records** | **60** |
| Skill mappings | 257 |
| Pipeline runtime | ~0.016s |

---

## 7. Task 2 — n8n Automation

### Objective
Build one working automation connected to the database.

### Automation Chosen
LLM-based skill categorization: a flow that reads each candidate from `consultbae.db`, sends their skills to an LLM, and writes a skill category tag (`automation-heavy`, `web-dev`, `data`, etc.) back to the database.

> **Workflow JSON:** `n8n/workflow.json`
> *(See n8n folder for the exported workflow and setup instructions)*

---

## 8. Task 3 — Audio Collection App

### Objective
A web app where gig workers submit audio recordings. Every submission automatically extracts audio metadata and a noise quality estimate.

### Application Flow

1. Worker lands on `/` — enters name and phone number
2. Records audio in-browser via MediaRecorder API OR uploads an audio file
3. Submits — audio saved to `audio_app/static/uploads/`
4. Server extracts metadata and runs noise analysis
5. Record written to `audio_submissions` table, linked to `candidates` via phone lookup
6. Worker can visit `/submissions` to see all entries with a play button

### Audio Upload / Recording

- Browser records in WebM/Opus format via `getUserMedia`
- File uploads supported for mp3, wav, mp4, webm, ogg, m4a
- 20 MB server-side limit enforced

### Audio Metadata Extraction

All extraction done in `audio_app/audio_processor.py` using `pydub` + `static-ffmpeg`:

| Field | Method |
|---|---|
| Duration | `len(AudioSegment) / 1000` |
| Sample Rate | `AudioSegment.frame_rate / 1000` |
| Bitrate | `(file_size_bytes × 8) / duration_seconds / 1000` |
| Loudness (dBFS) | `AudioSegment.dBFS` |
| Noise Quality | Custom FFT analysis (see below) |

### Noise / Quality Estimate (Bonus)

A 4-phase algorithm that doesn't rely on any external ML model or API — runs fully in-process in ~0.3 seconds:

**Phase 1 — Dynamic Range Guard**
If the audio has less than 18 dB of dynamic range and peaks below -20 dBFS, it's constant ambient noise with no speech. Return `Noisy` immediately. This catches fan-only recordings.

**Phase 2a — Voice Activity Detection (VAD)**
Audio sliced into 30ms frames (ITU standard frame size). Frames above the 75th percentile energy threshold classified as speech frames. The rest are noise frames.

**Phase 2b — Voice Band Energy Ratio (FFT)**
Full-file FFT computed on the mono waveform. Energy split across three bands:
- Voice band: 300–3400 Hz (where human speech lives)
- Rumble: < 300 Hz (fan hum, bass)
- Hiss: > 4000 Hz (fan hiss, high-frequency noise)

If voice band energy > 40% of total AND hiss < 25% → likely clean speech. If hiss dominates → noise.

**Phase 2c — Spectral Flatness Measure (SFM)**
On each speech frame: `geometric_mean(spectrum) / arithmetic_mean(spectrum)`. Clean harmonic speech has SFM < 0.20 (peaked spectrum). Broadband noise like a fan has SFM > 0.35 (flat spectrum).

**Phase 3 — Browser Noise Suppression Detection**
Chrome/Safari apply aggressive noise gating via `getUserMedia`. This creates abnormally dead-silent frames (< -60 dBFS) during pauses. If > 30% of frames are dead silent, the browser noise suppressor is working hard — flag as a signal that the room was noisy.

**Phase 4 — Weighted Score**

| Signal | Weight |
|---|---|
| Voice Band Ratio | 45% |
| Spectral Flatness | 20% |
| Browser NS Signature | 20% |
| Noise Floor Level | 15% |

Score > 0.65 → **Clear** · Score > 0.40 → **Moderate** · Below → **Noisy**

> Note: Microsoft's DNSMOS P.835 ONNX neural network was evaluated and rejected. It gave browser-recorded WebM files worse scores than actual noisy recordings because it was trained on uncompressed studio WAV files and gets confused by WebM compression artifacts. The custom FFT approach above correctly classified all test recordings.

### Running the Application

```bash
python3 -m flask --app audio_app/app.py run --port 5001
```

Visit: http://127.0.0.1:5001

---

## 9. Task 4 — Data Quality Report

### Summary

106 raw rows came in across 3 files. 3 structural issues were fixed before normalization even started. 9 categories of semantic/formatting issues were normalized. 43 duplicate clusters were resolved. 60 unique golden records came out the other side.

The most interesting issues:
- Source 2 had a **column-shift bug** where the skill field leaked into the email column for rows with more comma-separated values than expected
- Source 1 mixed CTC formats: `4.2` (lakhs) vs `417964` (absolute INR) — the distinction required checking whether the value was a small float (< 100) or a large integer
- Source 3 used `alt.` and `old.` email prefixes that would break entity matching unless stripped

→ **[Full detailed report: reports/data_issues_report.md](reports/data_issues_report.md)**

---

## 10. Task 5 — Scalability Analysis

### Scenario: 5,000 Workers Over a Weekend

### What Breaks First

**Storage:** 5,000 × 4 MB average = ~20 GB of audio files. Render free tier has 1 GB disk. We'd fill it within the first 200 submissions. Also, Render wipes the disk on every deploy — every pushed bug fix deletes all uploaded audio.

**Database:** SQLite is a single-writer file. Under concurrent submissions it creates a queue. At 60-80 concurrent users during peak hours, requests start timing out and DB writes fail silently — the file is saved but the record is never written.

**Uploads:** Flask's dev server is single-threaded. During FFT processing (~0.3s per file) the server is completely blocked. At 50 concurrent users, half of them time out and resubmit, creating duplicates.

**Audio Processing:** The FFT runs fine at this scale. The only risk is someone uploading a 10-minute file — FFT time scales linearly with duration and would block the thread for several seconds. No file size or duration limit is enforced server-side right now.

**Duplicate Submissions:** Zero duplicate prevention currently. A browser glitch, back button, or double-click creates two identical entries. At 5,000 people this happens constantly.

**Cost:** Total monthly cost to fix everything: ~$7-10/month (Render Starter + Cloudflare R2).

### Recommended Changes Before Launch

1. SQLite → Supabase Postgres (concurrent writes, 1 hour of work)
2. Local disk → Cloudflare R2 for file storage (survives deploys, 2 hours)
3. Run with `gunicorn -w 4` instead of Flask dev server (10 minutes)
4. Async audio processing — return "received" immediately, process in background (prevents timeouts)
5. Duplicate check: reject same phone within 60-second window (30 minutes)
6. Server-side file size limit (already have 20 MB cap) and duration limit (add < 3 min check)

→ **[Full analysis: reports/scale_analysis.md](reports/scale_analysis.md)**

---

## 11. Stuck Log

### Challenge 1 — Flask app returning 500 on every submission

The Flask `/submit` route was crashing with a 500 error on every single audio upload. Checked the logs and saw a SQL error — it was querying `c.name` but the `candidates` table column is actually called `full_name`. This was a simple column name mismatch but it took a few minutes to catch because Flask's default error page didn't show the full SQL traceback.

What I did: Added `print(e)` inside the except block temporarily to get the raw error, saw the column name, fixed it. Then moved the debug print to proper Flask error logging.

What I rejected: I briefly considered changing the DB schema column name to `name` to match the code. That would've been wrong — the schema was already deployed and used across multiple queries. Fix the code, not the contract.

### Challenge 2 — Fan recording was being graded "Clear"

After implementing the basic SNR check, I tested it against a real fan recording and it came back as "Clear" when it should clearly be "Noisy". The problem was that Chrome's `getUserMedia` applies noise suppression by default. That suppression dropped the noise floor to -54 dBFS during silence, making the fan sound like a quiet room to a naive peak-to-floor calculation.

I disabled the browser noise suppression in JavaScript first (`noiseSuppression: false`), but that made it worse in the opposite direction. The real fix was to not rely on the noise floor at all and instead look at the *frequency content* of the audio using FFT. Fan noise concentrates above 4000 Hz. Human speech concentrates between 300–3400 Hz. That distinction is immune to whatever the browser does to the volume levels.

Searched: "how to detect background noise in audio python without reference signal", "spectral flatness measure noise detection", read through the WebRTC VAD source code to understand how Google does frame classification.

Rejected: Using Microsoft's DNSMOS ONNX neural network. Tested it against the actual browser recordings and it gave the clean speech recording a worse score than the fan recording because it was trained on studio WAV files and gets confused by WebM compression artifacts.

### Challenge 3 — Fan-only recording still marked Clear after the FFT

After adding the FFT voice band ratio check, a fan-only recording (no speech, just loud fan) was still slipping through as "Clear" because the adaptive VAD threshold classified the top 25% of constant fan noise as "speech frames". With no real silence in the recording, the noise floor defaulted to -60 dBFS (artificially good), and the total score came out as Clear.

The fix was a dynamic range guard before any of the FFT logic runs: if the loudest and quietest frames are within 18 dB of each other AND the peak never goes above -20 dBFS, there's no real speech in the recording — it's constant ambient noise. That guard runs in 3 lines of code and catches the case correctly.

What I found: Real speech has 25-40 dB of dynamic range because you speak and then pause. Constant fan noise has 10-15 dB of range because it never stops.

---

## 12. Testing & Validation

### Task 1 Tests

Re-run the pipeline multiple times to verify idempotency:
```bash
python3 -m pipeline.run_pipeline
python3 -m pipeline.run_pipeline  # must produce identical results
```

Check output counts:
```bash
sqlite3 db/consultbae.db "SELECT COUNT(*) FROM candidates;"        # expect 60
sqlite3 db/consultbae.db "SELECT COUNT(*) FROM candidate_skills;"  # expect 257
```

### Task 3 Tests

All 4 test recordings classified correctly:

| Recording | Expected | Got |
|---|---|---|
| Clear speech, quiet room | Clear | Clear ✅ |
| Pure background noise, no speech | Noisy | Noisy ✅ |
| Speaking with fan running | Moderate | Moderate ✅ |
| Fan only, no speech | Noisy | Noisy ✅ |

---

## 13. Known Limitations

- **n8n workflow** requires n8n to be running locally. See `n8n/` folder for setup.
- **Audio app stores files locally** — not suitable for multi-server deployment without moving to S3 (see Task 5).
- **SQLite concurrency** — fine for local demo, breaks under real concurrent load (see Task 5).
- **FFT noise detection** was calibrated on laptop microphone + Chrome WebM recordings. Different microphones or recording hardware will produce different frequency profiles and may need threshold re-calibration.
- **No authentication** on the submissions page — anyone who knows the URL can see all submissions.

---

## 14. Submission

- **GitHub Repository:** https://github.com/sahiltolani30/SahilTolani_ConsultBae_Assignment
- **Demo Video:** *(link to be added)*

---

## 15. Author

**Sahil Tolani**
sahiltolani30@gmail.com
