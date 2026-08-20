"""
n8n Bridge API — Task 2B (v2 — upgraded workflow)
---------------------------------------------------
Bridges n8n ↔ SQLite for the LLM Skill Tagger workflow.

Endpoints:
  GET  /api/health
  GET  /api/candidates?untagged=true
  POST /api/candidates/<id>/tag      { skill_category, confidence, needs_review }
  GET  /api/results

v2 changes (matching upgraded n8n workflow):
  - /tag now accepts confidence (float), needs_review (bool),
    reasoning (str), source (str) from the Vertex AI output parser.
  - /results returns confidence and needs_review counts in the summary.

Usage:
  cd SahilTolani_ConsultBae_Assignment
  python3 -m n8n_api.app   →  http://localhost:5001
  /tmp/cloudflared tunnel --url http://localhost:5001 --no-autoupdate
"""

import os
import sqlite3
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Path to the SQLite DB — relative to project root
_HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", os.path.join(_HERE, "..", "db", "consultbae.db"))


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ─────────────────────────────────────────────
# GET /api/health
# ─────────────────────────────────────────────
@app.route("/api/health", methods=["GET"])
def health():
    """Quick liveness check used by n8n before the workflow starts."""
    return jsonify({"status": "ok", "db": DB_PATH})


# ─────────────────────────────────────────────
# GET /api/candidates?untagged=true
# Returns candidates as JSON array for n8n to iterate.
# ─────────────────────────────────────────────
@app.route("/api/candidates", methods=["GET"])
def get_candidates():
    untagged_only = request.args.get("untagged", "false").lower() == "true"
    conn = get_conn()
    try:
        if untagged_only:
            rows = conn.execute(
                """
                SELECT id, full_name, skills, skill_category
                FROM   candidates
                WHERE  skill_category IS NULL
                  AND  skills IS NOT NULL
                  AND  skills != ''
                ORDER  BY id
                """
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, full_name, skills, skill_category
                FROM   candidates
                ORDER  BY id
                """
            ).fetchall()
    finally:
        conn.close()

    result = []
    for r in rows:
        result.append({
            "id":             r["id"],
            "full_name":      r["full_name"],
            # skills stored as pipe-separated — convert to comma list for LLM readability
            "skills":         (r["skills"] or "").replace("|", ", "),
            "skill_category": r["skill_category"],
        })

    return jsonify(result)


# ─────────────────────────────────────────────
# POST /api/candidates/<id>/tag
# Body (v2): {
#   "skill_category": "automation-heavy",  -- required
#   "confidence":     0.92,                -- optional float 0-1
#   "needs_review":   false,               -- optional bool
#   "reasoning":      "...",               -- optional string
#   "source":         "llm"               -- optional: llm | keyword-fallback | none
# }
# ─────────────────────────────────────────────
@app.route("/api/candidates/<int:candidate_id>/tag", methods=["POST"])
def tag_candidate(candidate_id: int):
    data = request.get_json(silent=True) or {}
    skill_category = str(data.get("skill_category", "")).strip()

    VALID = {"automation-heavy", "web-dev", "data", "fullstack", "devops", "other"}
    if not skill_category:
        return jsonify({"error": "skill_category is required"}), 400
    if skill_category not in VALID:
        skill_category = "other"  # sanitise LLM drift

    # Optional v2 fields from the Vertex AI output parser
    confidence   = data.get("confidence")
    needs_review = data.get("needs_review")
    reasoning    = data.get("reasoning")
    source       = data.get("source")

    # Coerce types safely
    try:
        confidence = float(confidence) if confidence is not None else None
    except (ValueError, TypeError):
        confidence = None

    needs_review_int = 1 if needs_review else 0

    conn = get_conn()
    try:
        conn.execute(
            """UPDATE candidates
               SET skill_category = ?,
                   confidence     = ?,
                   needs_review   = ?,
                   tag_reasoning  = ?,
                   tag_source     = ?
               WHERE id = ?""",
            (skill_category, confidence, needs_review_int, reasoning, source, candidate_id),
        )
        conn.commit()
        affected = conn.execute("SELECT changes()").fetchone()[0]
    finally:
        conn.close()

    if affected == 0:
        return jsonify({"error": f"No candidate with id={candidate_id}"}), 404

    return jsonify({
        "ok":             True,
        "id":             candidate_id,
        "skill_category": skill_category,
        "confidence":     confidence,
        "needs_review":   bool(needs_review),
    })


# ─────────────────────────────────────────────
# GET /api/results  — final tagged results + run stats
# ─────────────────────────────────────────────
@app.route("/api/results", methods=["GET"])
def results():
    """Summary of tagging results — categories, confidence, needs_review counts."""
    conn = get_conn()
    try:
        summary = conn.execute(
            """
            SELECT   skill_category,
                     COUNT(*)                                      AS count,
                     ROUND(AVG(confidence), 2)                     AS avg_confidence,
                     SUM(CASE WHEN needs_review = 1 THEN 1 ELSE 0 END) AS needs_review_count
            FROM     candidates
            GROUP BY skill_category
            ORDER BY count DESC
            """
        ).fetchall()
        totals = conn.execute(
            """
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN skill_category IS NOT NULL THEN 1 ELSE 0 END) AS tagged,
                   SUM(CASE WHEN needs_review  = 1          THEN 1 ELSE 0 END) AS needs_review,
                   SUM(CASE WHEN skill_category IS NULL      THEN 1 ELSE 0 END) AS untagged
            FROM candidates
            """
        ).fetchone()
        all_rows = conn.execute(
            """SELECT id, full_name, skill_category, confidence,
                      needs_review, tag_source, tag_reasoning
               FROM candidates ORDER BY skill_category, id"""
        ).fetchall()
    finally:
        conn.close()

    return jsonify({
        "totals":     dict(totals),
        "by_category": [dict(r) for r in summary],
        "candidates": [dict(r) for r in all_rows],
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
