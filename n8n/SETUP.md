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

## Set up TWO things before running

### 1. Groq API Key (in the HTTP Request node)
- Click the **"Tag Skills with Groq LLM"** node
- Find the Authorization header value field
- Replace `YOUR_GROQ_API_KEY_HERE` with your actual Groq key from console.groq.com
- Free API key, no credit card needed

### 2. SQLite Credential
The workflow needs to know where your database file is.

1. In n8n, go to **Credentials** (left sidebar) → **Add Credential** → search "SQLite"
2. Set **Database** to the absolute path of your db file:
   ```
   /ABSOLUTE/PATH/TO/SahilTolani_ConsultBae_Assignment/db/consultbae.db
   ```
3. Save. Name it **"ConsultBae SQLite DB"**
4. Click each SQLite node → select this credential.

## Run it
Click **▶ Run Tagger** → **Execute Workflow**

Watch the execution. After ~30 seconds, all 60 candidates will have `skill_category` set.

## Verify results
```bash
sqlite3 db/consultbae.db "SELECT full_name, skills, skill_category FROM candidates LIMIT 10;"
```
