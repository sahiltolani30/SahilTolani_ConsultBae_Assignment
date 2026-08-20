import os
import sqlite3
import time
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, jsonify
from flask_cors import CORS
from .audio_processor import extract_audio_features

app = Flask(__name__)
CORS(app)
app.secret_key = 'super_secret_consultbae_key'
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024 # 20MB limit

# Ensure paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, '..', 'db', 'consultbae.db')
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def normalize_phone(phone: str) -> str:
    """Minimal normalize to match Task 1"""
    import re
    digits = re.sub(r'\D', '', str(phone))
    if len(digits) > 10 and digits.startswith('91'):
        digits = digits[2:]
    elif len(digits) > 10 and digits.startswith('0'):
        digits = digits[1:]
    return digits[-10:] if len(digits) >= 10 else digits

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/submit', methods=['POST'])
def submit():
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip().lower()
    phone = request.form.get('phone', '').strip()
    
    if not name or not phone or not email:
        flash('Name, email, and phone are required.', 'error')
        return redirect(url_for('index'))
        
    if 'audio' not in request.files:
        flash('No audio file provided.', 'error')
        return redirect(url_for('index'))
        
    file = request.files['audio']
    if file.filename == '':
        flash('No selected file.', 'error')
        return redirect(url_for('index'))
        
    # Save file
    norm_phone = normalize_phone(phone)
    ext = 'webm' if 'webm' in file.filename else file.filename.rsplit('.', 1)[-1]
    filename = secure_filename(f"{norm_phone}_{int(time.time())}.{ext}")
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    
    # Process audio
    try:
        features = extract_audio_features(filepath)
    except Exception as e:
        flash(f'Error processing audio: {e}', 'error')
        return redirect(url_for('index'))
        
    if features['duration_seconds'] < 5.0:
        if os.path.exists(filepath):
            os.remove(filepath)
        flash('Audio recording is too short. Please record for at least 5 seconds.', 'error')
        return redirect(url_for('index'))
        
    # Database
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Find candidate
    cursor.execute('SELECT id, email FROM candidates WHERE phone = ?', (norm_phone,))
    candidate = cursor.fetchone()
    
    if candidate:
        candidate_id = candidate['id']
        if not candidate['email'] and email:
            cursor.execute('UPDATE candidates SET email = ? WHERE id = ?', (email, candidate_id))
    else:
        # Create minimal candidate row so FK doesn't fail or leave it orphaned
        try:
            cursor.execute('''
                INSERT INTO candidates (full_name, phone, email, sources) 
                VALUES (?, ?, ?, ?)
            ''', (name, norm_phone, email, 'audio_app'))
            candidate_id = cursor.lastrowid
        except sqlite3.IntegrityError:
            cursor.execute('SELECT id FROM candidates WHERE email = ?', (email,))
            existing = cursor.fetchone()
            if existing:
                candidate_id = existing['id']
            else:
                flash('Database conflict. Please check your inputs.', 'error')
                return redirect(url_for('index'))
        
    # Insert submission
    cursor.execute('''
        INSERT INTO audio_submissions 
        (candidate_id, name, phone, file_path, duration_seconds, sample_rate_khz, bitrate_kbps, loudness_db, noise_quality_estimate)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        candidate_id, name, phone, filename, 
        features['duration_seconds'], features['sample_rate_khz'],
        features['bitrate_kbps'], features['loudness_db'], features['noise_quality_estimate']
    ))
    conn.commit()
    conn.close()
    
    # Non-blocking webhook fire to n8n Quality Watchdog
    n8n_webhook = os.environ.get('N8N_WATCHDOG_WEBHOOK_URL', '')
    if n8n_webhook:
        import json, urllib.request
        payload = json.dumps({
            'name': name,
            'email': email,
            'phone': norm_phone,
            'noise_quality': features['noise_quality_estimate'],
            'duration_seconds': features['duration_seconds'],
            'candidate_id': candidate_id,
        }).encode()
        try:
            urllib.request.urlopen(
                urllib.request.Request(
                    n8n_webhook, data=payload,
                    headers={'Content-Type': 'application/json'}
                ), timeout=3
            )
        except Exception as e:
            print(f"Webhook failed (non-blocking): {e}")
    
    flash('Audio submitted successfully!', 'success')
    return redirect(url_for('submissions'))

@app.route('/submissions')
def submissions():
    conn = get_db_connection()
    subs = conn.execute('''
        SELECT s.*, c.full_name as candidate_name
        FROM audio_submissions s
        LEFT JOIN candidates c ON s.candidate_id = c.id
        ORDER BY s.submitted_at DESC
    ''').fetchall()
    conn.close()
    return render_template('submissions.html', submissions=subs)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/api/stats')
def api_stats():
    """Quick stats endpoint — shows submission and candidate counts at a glance."""
    conn = get_db_connection()
    stats = {
        'total_candidates': conn.execute('SELECT COUNT(*) FROM candidates').fetchone()[0],
        'total_submissions': conn.execute('SELECT COUNT(*) FROM audio_submissions').fetchone()[0],
        'quality_breakdown': dict(conn.execute(
            'SELECT noise_quality_estimate, COUNT(*) FROM audio_submissions GROUP BY noise_quality_estimate'
        ).fetchall()),
    }
    conn.close()
    return jsonify(stats)

@app.route('/api/worker-history')
def worker_history():
    """n8n reads this to decide: tip email or flag for review."""
    phone = normalize_phone(request.args.get('phone', ''))
    candidate_id = request.args.get('candidate_id', '')
    conn = get_db_connection()
    if candidate_id:
        rows = conn.execute(
            '''SELECT noise_quality_estimate FROM audio_submissions
               WHERE candidate_id = ? ORDER BY submitted_at DESC''',
            (candidate_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            '''SELECT noise_quality_estimate FROM audio_submissions
               WHERE phone = ? ORDER BY submitted_at DESC''',
            (phone,)
        ).fetchall()
    conn.close()
    total = len(rows)
    noisy_count = sum(1 for r in rows if r['noise_quality_estimate'] == 'Noisy')
    return jsonify({
        'phone': phone,
        'candidate_id': candidate_id,
        'total_submissions': total,
        'noisy_count': noisy_count,
        'is_repeat_offender': noisy_count >= 3
    })

@app.route('/api/worker-flag', methods=['POST'])
def worker_flag():
    """n8n calls this to flag a repeat-offender worker in the DB."""
    data = request.get_json(silent=True) or {}
    candidate_id = data.get('candidate_id')
    reason = data.get('reason', '3+ noisy submissions')
    if not candidate_id:
        return jsonify({'error': 'candidate_id required'}), 400
    conn = get_db_connection()
    conn.execute(
        'UPDATE candidates SET audio_flagged = 1, audio_flag_reason = ? WHERE id = ?',
        (reason, candidate_id)
    )
    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'candidate_id': candidate_id, 'flagged': True})

# ─────────────────────────────────────────────
# n8n Bridge Endpoints (Task 2B)
# ─────────────────────────────────────────────

@app.route("/api/health", methods=["GET"])
def health():
    """Quick liveness check used by n8n before the workflow starts."""
    return jsonify({"status": "ok", "db": DB_PATH})

@app.route("/api/candidates", methods=["GET"])
def get_candidates():
    untagged_only = request.args.get("untagged", "false").lower() == "true"
    conn = get_db_connection()
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
            "skills":         (r["skills"] or "").replace("|", ", "),
            "skill_category": r["skill_category"],
        })

    return jsonify(result)

@app.route("/api/candidates/<int:candidate_id>/tag", methods=["POST"])
def tag_candidate(candidate_id: int):
    data = request.get_json(silent=True) or {}
    skill_category = str(data.get("skill_category", "")).strip()

    VALID = {"automation-heavy", "web-dev", "data", "fullstack", "devops", "other"}
    if not skill_category:
        return jsonify({"error": "skill_category is required"}), 400
    if skill_category not in VALID:
        skill_category = "other"  # sanitise LLM drift

    confidence   = data.get("confidence")
    needs_review = data.get("needs_review")
    reasoning    = data.get("reasoning")
    source       = data.get("source")

    try:
        confidence = float(confidence) if confidence is not None else None
    except (ValueError, TypeError):
        confidence = None

    needs_review_int = 1 if needs_review else 0

    conn = get_db_connection()
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

@app.route("/api/results", methods=["GET"])
def results():
    """Summary of tagging results — categories, confidence, needs_review counts."""
    conn = get_db_connection()
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

if __name__ == '__main__':
    app.run(debug=True, port=5001)
