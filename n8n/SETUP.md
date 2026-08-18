# n8n Workflow Setup

## What this workflow does
Reads all 60 candidates from `consultbae.db`, sends each person's skills to the
Groq LLM (llama-3.1-8b-instant), gets back a category tag, and writes it to the DB.

Categories: `automation-heavy` | `web-dev` | `data` | `design` | `full-stack` | `other`

## Start n8n
```bash
npx n8n
```
Open http://localhost:5678

## Import the workflow
1. Click **+ New Workflow** → top right menu → **Import from File**
2. Select `n8n/workflow.json`

## Set up ONE credential (SQLite)
The workflow needs to know where your database file is.

1. In n8n, go to **Credentials** (left sidebar) → **Add Credential** → search "SQLite"
2. Set **Database** to the absolute path of your db file:
   `/Users/YOUR_USERNAME/Sahil/ConsultBae_assignmet/SahilTolani_ConsultBae_Assignment/db/consultbae.db`
3. Save. Name it **"ConsultBae SQLite DB"**
4. Go back to the workflow. Click each SQLite node → select the credential you just created.

## Run it
Click **▶ Run Tagger** → **Execute Workflow**

Watch the execution. After ~30 seconds, all 60 candidates will have `skill_category` set.

## Verify
```bash
sqlite3 db/consultbae.db "SELECT full_name, skills, skill_category FROM candidates LIMIT 10;"
```
