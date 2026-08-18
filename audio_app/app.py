import os
import sqlite3
import time
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from .audio_processor import extract_audio_features

app = Flask(__name__)
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
    phone = request.form.get('phone', '').strip()
    
    if not name or not phone:
        flash('Name and phone are required.', 'error')
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
        
    # Database
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Find candidate
    cursor.execute('SELECT id FROM candidates WHERE phone = ?', (norm_phone,))
    candidate = cursor.fetchone()
    
    if candidate:
        candidate_id = candidate['id']
    else:
        # Create minimal candidate row so FK doesn't fail or leave it orphaned
        cursor.execute('''
            INSERT INTO candidates (full_name, phone, sources) 
            VALUES (?, ?, ?)
        ''', (name, norm_phone, 'audio_app'))
        candidate_id = cursor.lastrowid
        
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

if __name__ == '__main__':
    app.run(debug=True, port=5000)
