# Sahil Tolani — ConsultBae AI Automation Assignment

This repository contains the full end-to-end solution for the ConsultBae Take-Home Assignment, including:
1. A data engineering pipeline to clean and merge messy CSVs (Task 1)
2. An n8n workflow for automated skill categorization (Task 2)
3. A Flask-based audio collection app (Task 3)
4. A comprehensive data issues audit report (Task 4)
5. A system architecture scale analysis (Task 5)

## Setup Instructions

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the data pipeline (Task 1):
   ```bash
   python -m pipeline.run_pipeline
   ```
   *This will process the data in `data/`, create the SQLite database at `db/consultbae.db`, and generate the data issues report.*

## Stuck Log
*(To be filled during execution)*
