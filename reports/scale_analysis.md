# Task 5 — What Happens When 5,000 Workers Hit This App Over a Weekend

I built this app, so I know exactly where the cracks are. Let me be honest about it.

---

## What Breaks First: SQLite

SQLite is a file. One file. One writer at a time.

When two workers submit audio at the exact same second, SQLite makes one of them wait. When ten submit at the same second, nine of them are queued behind the first. At 5,000 people over a weekend that's maybe 60-80 people active at any peak hour. That queue turns into timeouts. Requests start failing silently — the audio file saved to disk, but the DB write never completed. The worker thinks they submitted, but they don't show up in the system.

**Fix:** Move to Postgres. It handles concurrent writes properly. Supabase gives you a managed Postgres instance free. A 15-minute migration.

---

## What Breaks Second: The Disk

Every WebM file coming out of Chrome is roughly 3-5 MB for a 5-6 second recording.

5,000 workers × 4 MB average = **~20 GB** of audio files.

This app currently writes every file to `audio_app/static/uploads/` on the server's local disk. The Render free tier has 1 GB of disk. We'd fill it within the first 200 submissions and then every upload after that fails with a "disk full" error that we're not even catching properly.

Also, Render's free tier wipes the disk on every deploy. So every time I push a bug fix, every uploaded file disappears.

**Fix:** Stream uploads directly to S3 or Cloudflare R2 (R2 has no egress fees, free for 10 GB). The file never touches our server. Store the S3 URL in the DB instead of a local path. Cloudflare R2 would cost literally zero dollars for this scale.

---

## What Breaks Third: The Server Itself

Flask's built-in development server is single-threaded. One request at a time.

When a worker submits audio, the server has to:
1. Receive the full file upload (network time)
2. Run the FFT analysis on it (CPU time, ~0.3-0.5 seconds)
3. Write to the DB
4. Send back a response

During step 2, the server is blocked. Nobody else can submit. At 50 concurrent users, this means 50 people are staring at a loading spinner, and half of them will give up and resubmit, creating duplicates.

**Fix 1:** Run with `gunicorn -w 4` (4 worker processes). Immediate fix, 10 minutes of work.

**Fix 2:** Make audio processing async. Accept the upload, return a "submission received" response immediately, then process the FFT in a background job queue. The worker sees instant confirmation. The analysis happens in the background.

---

## Duplicates

Right now there is zero duplicate prevention. If a worker's browser glitches and re-submits the form, they get two entries. If they hit the back button and submit again, they get two entries. Nothing stops this.

At 5,000 people, this is not an edge case — it will happen constantly.

**Fix:** Before inserting a new record, check if the same phone number submitted something in the last 60 seconds. If yes, ignore it. A single DB query. Also add a unique constraint on (phone, submitted_at) rounded to the nearest minute as a hard backstop.

---

## The FFT Processing Under Load

The frequency analysis we built works perfectly for one file at a time. Under load it stays fine because it's pure CPU math with no external calls — no network, no disk reads beyond what pydub already loaded.

The one real risk: if someone uploads a 10-minute audio file instead of a 6-second one, the FFT takes proportionally longer and blocks the thread. We should add a server-side file size limit (max 25 MB) and a duration check (reject anything over 3 minutes). Neither of those checks exist right now.

---

## Cost Estimate at This Scale

| Thing | Current | At Scale |
|---|---|---|
| Hosting | Render Free (sleeps, 512 MB RAM) | Render Starter $7/month (always on) |
| Database | SQLite file on disk | Supabase Free Postgres (500 MB) |
| File Storage | Local disk (breaks at ~200 files) | Cloudflare R2 (free up to 10 GB) |
| **Total** | **$0** | **~$7/month** |

5,000 files at 4 MB average = 20 GB. That's roughly $2/month on R2 after the free tier. Call it $10/month total. Very manageable.

---

## What I Would Actually Do Before Launch

In order of priority:

1. Switch SQLite → Supabase Postgres *(1 hour — prevents silent data loss)*
2. Switch local disk → Cloudflare R2 *(2 hours — prevents disk-full crashes)*
3. Add server-side file size + duration limit *(30 min — prevents one person blocking everyone)*
4. Add duplicate check by phone + 60-second window *(30 min)*
5. Deploy with `gunicorn -w 4` instead of Flask dev server *(10 min)*
6. Proper error page on the frontend — right now a failed upload shows a blank page *(1 hour)*

Steps 1–5 total: about 5-6 hours of work. After that the app would handle 5,000 submissions comfortably.
