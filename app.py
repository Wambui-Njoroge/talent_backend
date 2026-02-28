# app.py
from flask import Flask, request, jsonify, send_from_directory, url_for
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
import traceback
import os
import uuid
from werkzeug.utils import secure_filename
import smtplib
from email.mime.text import MIMEText

# ---------- APP SETUP ----------
app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = "uploads"
UPLOAD_FOLDER_ABSOLUTE = os.path.abspath(UPLOAD_FOLDER)
os.makedirs(UPLOAD_FOLDER_ABSOLUTE, exist_ok=True)

# ---------- DATABASE CONFIG ----------
DB_HOST = "dpg-d69pq3a48b3s73baq6d0-a.oregon-postgres.render.com"
DB_NAME = "auditions_db"
DB_USER = "auditions_db_user"
DB_PASSWORD = "HGKUEBnw9mfZnWfXCkvvxlSiXJMT7uUw"
DB_PORT = 5432

def get_db_connection():
    try:
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
    except Exception as e:
        print("DB connection failed:", e)
        raise

# ---------- EMAIL FUNCTION ----------
def send_notification(participant_id, status, venue=None, date=None, time=None):
    if status.lower() == "approve" or status.lower() == "approved":
        message = f"Congratulations! Your audition is approved.\nVenue: {venue}\nDate: {date}\nTime: {time}"
    else:
        message = "We regret to inform you that your audition was not successful."

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO notifications (participant_id, message) VALUES (%s, %s)",
            (participant_id, message)
        )
        conn.commit()
        cur.close()
        conn.close()
        print("Notification saved to DB")
    except Exception as e:
        print("Notification failed:", e)

# ---------- DEBUG ENDPOINT ----------
@app.route('/debug/paths', methods=['GET'])
def debug_paths():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, participant_name, video_path, image_path, status
            FROM submissions
            ORDER BY id DESC
            LIMIT 10
        """)
        submissions = cur.fetchall()
        cur.close()
        conn.close()

        result = []
        for sub in submissions:
            video_paths_to_check = [
                os.path.join(UPLOAD_FOLDER_ABSOLUTE, sub['video_path']),
                sub['video_path']
            ]
            image_paths_to_check = [
                os.path.join(UPLOAD_FOLDER_ABSOLUTE, sub['image_path']),
                sub['image_path']
            ]

            video_exists = any(os.path.exists(path) for path in video_paths_to_check)
            image_exists = any(os.path.exists(path) for path in image_paths_to_check)

            video_url = url_for('uploaded_file', filename=os.path.basename(sub['video_path']), _external=True) if video_exists else None
            image_url = url_for('uploaded_file', filename=os.path.basename(sub['image_path']), _external=True) if image_exists else None

            result.append({
                "id": sub['id'],
                "participant_name": sub['participant_name'],
                "video_path_db": sub['video_path'],
                "image_path_db": sub['image_path'],
                "video_file_exists": video_exists,
                "image_file_exists": image_exists,
                "video_url": video_url,
                "image_url": image_url,
                "status": sub['status']
            })

        return jsonify({
            "success": True,
            "upload_folder": UPLOAD_FOLDER,
            "upload_folder_absolute": UPLOAD_FOLDER_ABSOLUTE,
            "upload_folder_exists": os.path.exists(UPLOAD_FOLDER_ABSOLUTE),
            "files_in_folder": os.listdir(UPLOAD_FOLDER_ABSOLUTE) if os.path.exists(UPLOAD_FOLDER_ABSOLUTE) else [],
            "submissions": result
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e), "traceback": traceback.format_exc()}), 500

# ---------- FILE SERVING ROUTE ----------
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    try:
        if '..' in filename or filename.startswith('/'):
            return "Invalid filename", 400
        return send_from_directory(UPLOAD_FOLDER_ABSOLUTE, filename)
    except Exception as e:
        print(f"Error serving file {filename}: {e}")
        return "File not found", 404

# ---------- GET FILE URL ENDPOINT ----------
@app.route('/get_file_url/<int:submission_id>/<string:file_type>')
def get_file_url(submission_id, file_type):
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        if file_type == 'video':
            cur.execute("SELECT video_path FROM submissions WHERE id = %s", (submission_id,))
        else:
            cur.execute("SELECT image_path FROM submissions WHERE id = %s", (submission_id,))

        result = cur.fetchone()
        cur.close()
        conn.close()

        if not result:
            return jsonify({"success": False, "message": "Submission not found"}), 404

        file_path = result['video_path'] if file_type == 'video' else result['image_path']
        filename = os.path.basename(file_path) if file_path else None
        full_path = os.path.join(UPLOAD_FOLDER_ABSOLUTE, filename) if filename else ""
        file_exists = os.path.exists(full_path)
        file_url = url_for('uploaded_file', filename=filename, _external=True) if file_exists else None

        return jsonify({
            "success": True,
            "file_url": file_url,
            "filename": filename,
            "original_path": file_path,
            "file_exists": file_exists,
            "full_path": full_path
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e), "traceback": traceback.format_exc()}), 500

# ---------- BASIC ROUTES ----------
@app.route('/')
def index():
    return jsonify({"message": "Server is running!"})

@app.route('/ping')
def ping():
    return {"status": "ok"}

# ---------- PARTICIPANT & ADMIN ROUTES ----------
@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        full_name = data.get("full_name")
        age = data.get("age")
        gender = data.get("gender")
        email = data.get("email")
        password = data.get("password")

        if not all([full_name, age, gender, email, password]):
            return jsonify({"success": False, "message": "Please fill all fields"}), 400

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO participants (full_name, age, gender, email, password)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING participant_id
        """, (full_name, age, gender, email, password))
        participant_id = cur.fetchone()["participant_id"]
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"success": True, "message": "Registration successful!", "participant_id": participant_id})
    except psycopg2.IntegrityError:
        return jsonify({"success": False, "message": "Email already exists"}), 400
    except Exception as e:
        return jsonify({"success": False, "message": "Registration failed", "error": str(e)}), 500

@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        email = data.get("email")
        password = data.get("password")

        if not all([email, password]):
            return jsonify({"success": False, "message": "Please fill all fields"}), 400

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM participants WHERE email=%s AND password=%s", (email, password))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if user:
            return jsonify({"success": True, "message": "Login successful!", "participant_id": user["participant_id"]})
        else:
            return jsonify({"success": False, "message": "Invalid credentials"}), 401
    except Exception as e:
        return jsonify({"success": False, "message": "Login failed", "error": str(e)}), 500

@app.route('/admin_register', methods=['POST'])
def admin_register():
    try:
        data = request.get_json()
        full_name = data.get("full_name")
        email = data.get("email")
        password = data.get("password")

        if not all([full_name, email, password]):
            return jsonify({"success": False, "message": "Fill all fields"}), 400

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO admins (full_name, email, password)
            VALUES (%s, %s, %s)
            RETURNING admin_id
        """, (full_name, email, password))
        admin_id = cur.fetchone()["admin_id"]
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"success": True, "message": "Admin registered!", "admin_id": admin_id})
    except psycopg2.IntegrityError:
        return jsonify({"success": False, "message": "Email already exists"}), 400
    except Exception as e:
        return jsonify({"success": False, "message": "Registration failed", "error": str(e)}), 500

@app.route('/admin_login', methods=['POST'])
def admin_login():
    try:
        data = request.get_json()
        email = data.get("email")
        password = data.get("password")

        if not all([email, password]):
            return jsonify({"success": False, "message": "Fill all fields"}), 400

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM admins WHERE email=%s AND password=%s", (email, password))
        admin = cur.fetchone()
        cur.close()
        conn.close()

        if admin:
            return jsonify({"success": True, "message": "Login successful!", "admin_id": admin["admin_id"]})
        else:
            return jsonify({"success": False, "message": "Invalid credentials"}), 401
    except Exception as e:
        return jsonify({"success": False, "message": "Login failed", "error": str(e)}), 500

# ---------- AUDITIONS ----------
@app.route("/admin/post_audition", methods=["POST"])
def post_audition():
    try:
        data = request.get_json()
        title = data.get("title")
        description = data.get("description")
        audition_date = data.get("audition_date")
        location = data.get("location")
        created_by = data.get("created_by")  # admin_id

        if not all([title, description, audition_date, location, created_by]):
            return jsonify({"success": False, "message": "All fields are required"}), 400

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO auditions (title, description, audition_date, location, created_by)
            VALUES (%s,%s,%s,%s,%s)
        """, (title, description, audition_date, location, created_by))
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"success": True, "message": "Audition posted successfully!"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/auditions', methods=['GET'])
def get_auditions():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT audition_id, title, description, audition_date, location
            FROM auditions
            ORDER BY audition_id DESC
        """)
        auditions = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify({"success": True, "auditions": auditions})
    except Exception as e:
        return jsonify({"success": False, "auditions": [], "message": str(e)}), 500

# ---------- SUBMIT AUDITION ----------
@app.route('/submit_audition', methods=['POST'])
def submit_audition():
    try:
        name = request.form.get('name')
        age = request.form.get('age')
        gender = request.form.get('gender')
        email = request.form.get('email')
        participant_id = request.form.get('participant_id')
        audition_id = request.form.get('audition_id')

        video = request.files.get('video')
        image = request.files.get('image')

        if not all([name, age, gender, email, participant_id, audition_id, video, image]):
            return jsonify({"success": False, "message": "All fields are required"}), 400

        try:
            participant_id = int(participant_id)
            audition_id = int(audition_id)
            age = int(age)
        except (ValueError, TypeError):
            return jsonify({"success": False, "message": "IDs and age must be numbers"}), 400

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM auditions WHERE audition_id = %s", (audition_id,))
        if not cur.fetchone():
            return jsonify({"success": False, "message": f"Audition ID {audition_id} does not exist"}), 400

        video_filename = f"{uuid.uuid4()}_{secure_filename(video.filename)}"
        image_filename = f"{uuid.uuid4()}_{secure_filename(image.filename)}"

        video_path_full = os.path.join(UPLOAD_FOLDER_ABSOLUTE, video_filename)
        image_path_full = os.path.join(UPLOAD_FOLDER_ABSOLUTE, image_filename)

        video.save(video_path_full)
        image.save(image_path_full)

        print(f"Saved video: {video_filename}, exists: {os.path.exists(video_path_full)}")
        print(f"Saved image: {image_filename}, exists: {os.path.exists(image_path_full)}")

        cur.execute("""
            INSERT INTO submissions
            (participant_id, participant_name, participant_age, participant_gender,
             participant_email, audition_id, video_path, image_path, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (participant_id, name, age, gender, email, audition_id, video_filename, image_filename, 'pending'))

        submission_id = cur.fetchone()['id']
        conn.commit()
        cur.close()
        conn.close()

        video_url = url_for('uploaded_file', filename=video_filename, _external=True)
        image_url = url_for('uploaded_file', filename=image_filename, _external=True)

        return jsonify({
            "success": True,
            "message": "Submission successful!",
            "submission_id": submission_id,
            "video_url": video_url,
            "image_url": image_url,
            "video_filename": video_filename,
            "image_filename": image_filename
        })
    except Exception as e:
        return jsonify({"success": False, "message": "Server error", "error": str(e)}), 500

# ---------- ADMIN SUBMISSIONS ----------
@app.route('/admin/submissions', methods=['GET'])
def get_submissions():
    try:
        admin_id = request.args.get('admin_id')
        if not admin_id:
            return jsonify({"success": False, "message": "Admin ID required"}), 400
        try:
            admin_id = int(admin_id)
        except ValueError:
            return jsonify({"success": False, "message": "Admin ID must be an integer"}), 400

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT s.id, s.participant_id, s.participant_name, s.participant_age,
                   s.participant_gender, s.participant_email, s.video_path, s.image_path, s.status
            FROM submissions s
            JOIN auditions a ON s.audition_id = a.audition_id
            WHERE a.created_by = %s
            ORDER BY s.id DESC
        """, (admin_id,))
        rows = cur.fetchall()
        cur.close()
        conn.close()

        submissions = []
        for row in rows:
            video_filename = os.path.basename(row['video_path']) if row['video_path'] else None
            image_filename = os.path.basename(row['image_path']) if row['image_path'] else None

            video_full_path = os.path.join(UPLOAD_FOLDER_ABSOLUTE, video_filename) if video_filename else ""
            image_full_path = os.path.join(UPLOAD_FOLDER_ABSOLUTE, image_filename) if image_filename else ""

            video_exists = os.path.exists(video_full_path)
            image_exists = os.path.exists(image_full_path)

            video_url = url_for('uploaded_file', filename=video_filename, _external=True) if video_exists else None
            image_url = url_for('uploaded_file', filename=image_filename, _external=True) if image_exists else None

            submissions.append({
                "id": row.get("id"),
                "participant_id": row.get("participant_id"),
                "participant_name": row.get("participant_name"),
                "participant_age": row.get("participant_age"),
                "participant_gender": row.get("participant_gender"),
                "participant_email": row.get("participant_email"),
                "video_url": video_url,
                "image_url": image_url,
                "video_filename": video_filename,
                "image_filename": image_filename,
                "video_exists": video_exists,
                "image_exists": image_exists,
                "status": row.get("status", "pending")
            })

        return jsonify({"success": True, "submissions": submissions})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# ---------- NOTIFICATIONS ----------
@app.route("/notifications/<int:participant_id>", methods=["GET"])
def get_notifications(participant_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, message, is_read, created_at
            FROM notifications
            WHERE participant_id=%s
            ORDER BY created_at DESC
        """, (participant_id,))
        notifications = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify({"success": True, "notifications": notifications})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# ---------- APPROVE / REJECT SUBMISSION ----------
@app.route("/admin/submission_action", methods=["POST"])
def submission_action():
    try:
        data = request.get_json()
        submission_id = data.get("submission_id")
        action = data.get("action")  # "approve" or "reject"
        venue = data.get("venue")
        date = data.get("date")
        time = data.get("time")

        if not all([submission_id, action]) or action not in ["approve", "reject"]:
            return jsonify({"success": False, "message": "Invalid data"}), 400

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT participant_id FROM submissions WHERE id=%s", (submission_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({"success": False, "message": "Submission not found"}), 404

        participant_id = row["participant_id"]
        cur.execute("UPDATE submissions SET status=%s WHERE id=%s", (action, submission_id))
        conn.commit()
        cur.close()
        conn.close()

        send_notification(participant_id, action, venue=venue, date=date, time=time)

        return jsonify({"success": True, "message": f"Submission {action}d successfully!"})
    except Exception as e:
        return jsonify({"success": False, "message": "Server error", "error": str(e)}), 500

# ---------- MAIN ----------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
