# app.py
from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
import traceback
import os
from werkzeug.utils import secure_filename
import smtplib
from email.mime.text import MIMEText

# ---------- APP SETUP ----------
app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ---------- DATABASE CONFIG ----------
DB_HOST = "dpg-d69pq3a48b3s73baq6d0-a.oregon-postgres.render.com"
DB_NAME = "auditions_db"
DB_USER = "auditions_db_user"
DB_PASSWORD = "HGKUEBnw9mfZnWfXCkvvxlSiXJMT7uUw"
DB_PORT = 5432

def get_db_connection():
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        port=DB_PORT,
        sslmode='require',
        cursor_factory=RealDictCursor
    )
    return conn

# ---------- EMAIL FUNCTION ----------
def send_result_email(to_email, status, venue=None, date=None, time=None):
    if status.lower() == "approved":
        body = f"Congratulations! Your audition is approved.\nVenue: {venue}\nDate: {date}\nTime: {time}"
    else:
        body = "We regret to inform you that your audition was not successful."

    msg = MIMEText(body)
    msg['Subject'] = "Audition Result"
    msg['From'] = "admin@auditionapp.com"  # replace with real email
    msg['To'] = to_email

    # Optional: For testing
    try:
        with smtplib.SMTP('smtp.example.com', 587) as server:
            server.starttls()
            server.login("your_email@example.com", "your_email_password")
            server.send_message(msg)
    except Exception as e:
        print("Email sending failed:", e)

# -------------------- SUBMISSIONS --------------------
@app.route('/submit_audition', methods=['POST'])
def submit_audition():
    try:
        participant_id = request.form.get('participant_id')
        audition_id = request.form.get('audition_id')  # 👈 added
        name = request.form.get('name')
        age = request.form.get('age')
        gender = request.form.get('gender')
        email = request.form.get('email')

        video = request.files.get('video')
        image = request.files.get('image')

        if not all([participant_id, audition_id, name, age, gender, email, video, image]):
            return jsonify({"success": False, "message": "All fields required"}), 400

        video_filename = secure_filename(video.filename)
        image_filename = secure_filename(image.filename)
        video_path = os.path.join(UPLOAD_FOLDER, video_filename)
        image_path = os.path.join(UPLOAD_FOLDER, image_filename)

        video.save(video_path)
        image.save(image_path)

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO submissions
            (participant_id, audition_id, participant_name, participant_age, participant_gender, participant_email, video_path, image_path)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (participant_id, audition_id, name, age, gender, email, video_path, image_path))
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"success": True, "message": "Submission successful! Await results."})
    except Exception as e:
        print(traceback.format_exc())
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/admin/submissions/<int:admin_id>', methods=['GET'])
def get_submissions(admin_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT
                s.id,
                s.participant_name,
                s.participant_age,
                s.participant_gender,
                s.participant_email,
                s.video_path,
                s.image_path,
                s.status
            FROM submissions s
            JOIN auditions a ON s.audition_id = a.audition_id
            WHERE a.created_by = %s
            ORDER BY s.id DESC
        """, (admin_id,))

        rows = cur.fetchall()
        submissions = []
        for row in rows:
            submissions.append({
                "id": row["id"],
                "participant_name": row["participant_name"],
                "participant_age": row["participant_age"],
                "participant_gender": row["participant_gender"],
                "participant_email": row["participant_email"],
                "video_path": row["video_path"],
                "image_path": row["image_path"],
                "status": row["status"]
            })

        cur.close()
        conn.close()

        return jsonify({"success": True, "submissions": submissions})

    except Exception as e:
        print(traceback.format_exc())
        return jsonify({"success": False, "message": str(e)}), 500
