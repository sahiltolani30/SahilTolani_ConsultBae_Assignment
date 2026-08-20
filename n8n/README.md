# Task 2 — n8n Automation Workflows

This directory contains **two** separate n8n automation workflows. Both interact with the same SQLite database via our Flask backend, but they demonstrate different architectural patterns.

---

## Prerequisites — One-Time Credential Setup

Both workflows use **Google Vertex AI (Gemini)**. Task 2C additionally requires a **Gmail** account. Complete this one-time setup before importing either workflow.

### A. Enable Vertex AI on Google Cloud Console

1. Go to [https://console.cloud.google.com](https://console.cloud.google.com) and log in.
2. Select your project from the top dropdown (or create a new one).
3. In the left sidebar, go to **APIs & Services → Library**.
4. Search for **"Vertex AI API"** and click **Enable**.

### B. Create a Service Account & Download JSON Key

1. In Google Cloud Console, go to **IAM & Admin → Service Accounts**.
2. Click **+ Create Service Account**.
   - Name it something like `n8n-vertex-ai` and click **Create and Continue**.
3. Under **Grant this service account access to project**, select the role **Vertex AI User** and click **Done**.
4. Find your new service account in the list and click on it.
5. Go to the **Keys** tab → **Add Key → Create new key → JSON** → click **Create**.
6. A `.json` file will download automatically. Keep it safe — this contains your credentials.

### C. Add the Vertex AI Credential to n8n

1. In your n8n instance, go to **Credentials** (left sidebar) → **Add Credential**.
2. Search for **"Google Service Account"** and select it.
3. Open the downloaded `.json` file in any text editor.
   - Copy the value of `"client_email"` → paste it into the **Service Account Email** field in n8n.
   - Copy the full value of `"private_key"` (including `-----BEGIN PRIVATE KEY-----` and `-----END PRIVATE KEY-----`) → paste it into the **Private Key** field in n8n.
4. Click **Save**. This credential will now be available to all Vertex AI nodes.

---

## 1. Task 2B: LLM Skill Tagger (Batch Processing)
**File:** `skill_tagger_workflow.json`

### What it does:
A batch-processing flow that:
1. Fetches every untagged candidate from `consultbae.db`.
2. Sends their raw skills to **Google Vertex AI** (Gemini 2.5) for classification.
3. Automatically retries failed/rate-limited LLM calls up to 3 times with a 5-second backoff.
4. Writes a normalized `skill_category` tag back to the database.
*(Categories: `automation-heavy` | `web-dev` | `data` | `fullstack` | `devops` | `other`)*

### Setup & Run:
1. Complete **Prerequisite Sections A, B, and C** above.
2. Start the Flask server: `python3 -m flask --app audio_app/app.py run --port 5001`
3. Start a tunnel: `ngrok http 5001` (or cloudflare/pinggy). Copy the tunnel URL.
4. In n8n, go to **Workflows → Import from File** and upload `skill_tagger_workflow.json`.
5. Double-click the **"Run Config"** node and update the `apiBaseUrl` field to your tunnel URL.
6. Click any **"Vertex AI"** node on the canvas → in the **Credential** field, select the Google Service Account you saved in Step C.
7. Click **Execute Workflow (▶)** and watch each node turn green.

*(To verify results in terminal: `curl http://localhost:5001/api/results`)*

---

## 2. Task 2C: Audio Quality Watchdog (Event-Driven)
**File:** `audio_quality_watchdog.json`

### What it does:
A real-time escalation workflow triggered whenever a gig worker submits an audio recording on the web UI. It relies on a "strike system":
- **Strike 1 & 2 (Coaching):** Calls Google Vertex AI to generate a personalized coaching tip and sends it via **Gmail** to the worker.
- **Strike 3 (Escalation):** Makes an HTTP POST back to the Flask API to flag the worker's account (`audio_flagged = 1`), freezing it for human review.

### Step 1 — Vertex AI Credential
Complete **Prerequisite Sections A, B, and C** at the top of this file. The same service account credential works here.

### Step 2 — Link Your Gmail Account to n8n

1. In your n8n instance, go to **Credentials → Add Credential**.
2. Search for **"Gmail OAuth2"** and select it.
3. n8n will open a Google Sign-In popup. Log in with the Gmail account you want to send emails from.
4. Grant the requested permissions and click **Allow**.
5. n8n saves the credential automatically. Name it `Gmail account`.

### Step 3 — Import & Configure the Workflow

1. In n8n, go to **Workflows → Import from File** and upload `audio_quality_watchdog.json`.
2. Open the **"Fetch Worker History"** and **"Flag Worker"** nodes. Update the URLs to point to your Flask server:
   - *If n8n is local:* `http://localhost:5001` or `http://host.docker.internal:5001`
   - *If n8n is on the cloud:* your ngrok URL (e.g. `https://abc123.ngrok-free.app`)
3. Open the **"Generate Audio Tip"** node → click the **Credential** field → select your **Google Service Account**.
4. Open the **"Send Tip Email"** node → click the **Credential** field → select your **Gmail account**.
5. Open the **"Audio Submission Webhook"** node and copy the **Production Webhook URL**.

### Step 4 — Start Flask with the Webhook URL

```bash
export N8N_WATCHDOG_WEBHOOK_URL="YOUR_N8N_PRODUCTION_WEBHOOK_URL_HERE"
python3 -m flask --app audio_app/app.py run --port 5001
```

### Step 5 — Test the Flow

Open the frontend web app, record a noisy 5-second audio clip, and submit. Watch the n8n canvas execute automatically — no clicking required!

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `Skill Tagger: No candidates returned` | Run `UPDATE candidates SET skill_category = NULL;` in SQLite to reset tags |
| `Vertex AI 403 Forbidden` | Ensure Vertex AI API is enabled in Google Cloud Console and the service account has the "Vertex AI User" role |
| `Private key invalid` | Ensure you copied the full `private_key` value including `-----BEGIN PRIVATE KEY-----` and `-----END PRIVATE KEY-----` |
| `Gmail: OAuth not completing` | Make sure you are logged into the correct Google account in the browser where n8n is open |
| `Watchdog: Webhook not firing` | Ensure you exported `N8N_WATCHDOG_WEBHOOK_URL` *before* starting Flask |
| `Watchdog: HTTP Node fails with 403` | Free Cloudflare tunnels block bot API calls. Switch to `ngrok`. |
| `Watchdog: Connection Refused` | If n8n runs in Docker, use `host.docker.internal` instead of `localhost`. |

