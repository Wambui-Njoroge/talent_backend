# app.py
from flask import Flask, request, jsonify
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
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ---------- DATABASE CONFIG ----------
DB_HOST = "dpg-d69pq3a48b3s73baq6d0-a.oregon-postgres.render.com"
DB_NAME = "auditions_db"
DB_USER = "auditions_db_user"
DB_PASSWORD = "HGKUEBnw9mfZnWfXCkvvxlSiXJMT7uUw"
DB_PORT = 5432


from flask import send_from_directory

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)
def get_db_connection():
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT,
            sslmode='require',  # Important for Render
            cursor_factory=RealDictCursor
        )
        return conn
    except Exception as e:
        print("DB connection failed:", e)
        raise

# ---------- EMAIL FUNCTION ----------
def send_notification(participant_id, status, venue=None, date=None, time=None):
    if status.lower() == "approved":
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

# ---------- ROUTES ----------
@app.route('/')
def index():
    return jsonify({"message": "Server is running!"})

@app.route('/ping')
def ping():
    return {"status": "ok"}

# -------- PARTICIPANT REGISTRATION & LOGIN --------
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
        print("Error in /register:", traceback.format_exc())
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
        print("Error in /login:", traceback.format_exc())
        return jsonify({"success": False, "message": "Login failed", "error": str(e)}), 500

# -------- ADMIN REGISTRATION & LOGIN --------
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
        print("Error in /admin_register:", traceback.format_exc())
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
        print("Error in /admin_login:", traceback.format_exc())
        return jsonify({"success": False, "message": "Login failed", "error": str(e)}), 500

# -------- AUDITIONS --------
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
        print(traceback.format_exc())
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
        print(traceback.format_exc())
        return jsonify({"success": False, "auditions": [], "message": str(e)}), 500

# -------- SUBMIT AUDITION --------
@app.route('/submit_audition', methods=['POST'])
def submit_audition():
    try:
        # ---------- 1️⃣ Get form data ----------
        name = request.form.get('name')
        age = request.form.get('age')
        gender = request.form.get('gender')
        email = request.form.get('email')
        participant_id = request.form.get('participant_id')
        audition_id = request.form.get('audition_id')

        video = request.files.get('video')
        image = request.files.get('image')

        # ---------- 2️⃣ Validate required fields ----------
        if not all([name, age, gender, email, participant_id, audition_id, video, image]):
            return jsonify({"success": False, "message": "All fields are required"}), 400

        # ---------- 3️⃣ Convert IDs and age safely ----------
        try:
            participant_id = int(participant_id)
        except (ValueError, TypeError):
            return jsonify({"success": False, "message": "Invalid participant_id"}), 400

        try:
            audition_id = int(audition_id)
        except (ValueError, TypeError):
            return jsonify({"success": False, "message": "Invalid audition_id"}), 400

        try:
            age = int(age)
        except (ValueError, TypeError):
            return jsonify({"success": False, "message": "Age must be a number"}), 400

        # ---------- 4️⃣ Check audition exists ----------
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM auditions WHERE audition_id = %s", (audition_id,))
        if not cur.fetchone():
            return jsonify({"success": False, "message": f"Audition ID {audition_id} does not exist"}), 400

        # ---------- 5️⃣ Save uploaded files with unique filenames ----------
        video_filename = f"{uuid.uuid4()}_{secure_filename(video.filename)}"
        image_filename = f"{uuid.uuid4()}_{secure_filename(image.filename)}"
        video_path = os.path.join(UPLOAD_FOLDER, video_filename)
        image_path = os.path.join(UPLOAD_FOLDER, image_filename)
        video.save(video_path)
        image.save(image_path)

        # ---------- 6️⃣ Insert submission into DB ----------
        cur.execute("""
            INSERT INTO submissions
            (participant_id, participant_name, participant_age, participant_gender,
             participant_email, audition_id, video_path, image_path)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (participant_id, name, age, gender, email, audition_id, video_path, image_path))
        conn.commit()
        cur.close()
        conn.close()

        # ---------- 7️⃣ Return success ----------
        return jsonify({
            "success": True,
            "message": "Submission successful!",
            "video_path": video_path,   # optional for debugging
            "image_path": image_path
        })

    except Exception as e:
        print(traceback.format_exc())
        return jsonify({"success": False, "message": "Server error", "error": str(e)}), 500
# -------- ADMIN SUBMISSIONS --------
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
            # Safely unpack row values
            submissions.append({
                "id": row.get("id"),
                "participant_id": row.get("participant_id"),
                "participant_name": row.get("participant_name"),
                "participant_age": row.get("participant_age"),
                "participant_gender": row.get("participant_gender"),
                "participant_email": row.get("participant_email"),
                "video_path": row.get("video_path"),
                "image_path": row.get("image_path"),
                "status": row.get("status", "pending")
            })

        return jsonify({"success": True, "submissions": submissions})
    except Exception as e:
        print(traceback.format_exc())
        return jsonify({"success": False, "message": str(e)}), 50
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
        print(traceback.format_exc())
        return jsonify({"success": False, "message": str(e)}), 500
# ---------- APPROVE / REJECT SUBMISSION ----------
@app.route("/admin/submission_action", methods=["POST"])
def submission_action():
    try:
        data = request.get_json()
        submission_id = data.get("submission_id")
        action = data.get("action")  # "approve" or "reject"
        venue = data.get("venue")  # optional, only for approve
        date = data.get("date")    # optional, only for approve
        time = data.get("time")    # optional, only for approve

        if not all([submission_id, action]) or action not in ["approve", "reject"]:
            return jsonify({"success": False, "message": "Invalid data"}), 400

        conn = get_db_connection()
        cur = conn.cursor()

        # Fetch participant_id first
        cur.execute("SELECT participant_id FROM submissions WHERE id=%s", (submission_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({"success": False, "message": "Submission not found"}), 404

        participant_id = row["participant_id"]

        # Update submission status
        cur.execute(
            "UPDATE submissions SET status=%s WHERE id=%s",
            (action, submission_id)
        )
        conn.commit()
        cur.close()
        conn.close()

        # Send in-app notification
        send_notification(participant_id, action, venue=venue, date=date, time=time)

        return jsonify({"success": True, "message": f"Submission {action}d successfully!"})

    except Exception as e:
        print(traceback.format_exc())
        return jsonify({"success": False, "message": "Server error", "error": str(e)}), 500
# ---------- MAIN ----------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
