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
def send_result_email(to_email, status, venue=None, date=None, time=None):
    if status.lower() == "approved":
        body = f"Congratulations! Your audition is approved.\nVenue: {venue}\nDate: {date}\nTime: {time}"
    else:
        body = "We regret to inform you that your audition was not successful."

    msg = MIMEText(body)
    msg['Subject'] = "Audition Result"
    msg['From'] = "admin@auditionapp.com"  # replace with your email
    msg['To'] = to_email

    # Optional: For testing, comment out email sending or use real SMTP
    try:
        with smtplib.SMTP('smtp.example.com', 587) as server:
            server.starttls()
            server.login("your_email@example.com", "your_email_password")
            server.send_message(msg)
    except Exception as e:
        print("Email sending failed:", e)

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
        cur.execute(
            """
            INSERT INTO participants (full_name, age, gender, email, password)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING participant_id
            """,
            (full_name, age, gender, email, password)
        )
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
        cur.execute(
            "INSERT INTO admins (full_name, email, password) VALUES (%s, %s, %s) RETURNING admin_id",
            (full_name, email, password)
        )
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
        cur.execute(
            "INSERT INTO auditions (title, description, audition_date, location, created_by) VALUES (%s,%s,%s,%s,%s)",
            (title, description, audition_date, location, created_by)
        )
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
        cur.execute("SELECT * FROM auditions ORDER BY audition_id DESC")
        auditions = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify({"auditions": auditions, "success": True})
    except Exception as e:
        return jsonify({"auditions": [], "success": False, "message": str(e)})

# -------- SUBMISSIONS & RESULTS --------
@app.route('/submit_audition', methods=['POST'])
def submit_audition():
    try:
        name = request.form.get('name')
        age = request.form.get('age')
        gender = request.form.get('gender')
        email = request.form.get('email')
        participant_id = request.form.get('participant_id')

        video = request.files.get('video')
        image = request.files.get('image')

        if not all([name, age, gender, email, video, image]):
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
            (participant_id, participant_name, participant_age, participant_gender, participant_email, video_path, image_path)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (participant_id, name, age, gender, email, video_path, image_path))
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

        # Convert to JSON-friendly format
        submissions = []
        for row in rows:
            submissions.append({
                "id": row[0],
                "name": row[1],
                "age": row[2],
                "gender": row[3],
                "email": row[4],
                "video": row[5],
                "image": row[6],
                "status": row[7]
            })

        cur.close()
        conn.close()

        return jsonify({
            "success": True,
            "submissions": submissions
        })

    except Exception as e:
        print(traceback.format_exc())
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500
@app.route('/mark_result', methods=['POST'])
def mark_result():
    data = request.json
    application_id = data.get('application_id')
    status = data.get('status')
    venue = data.get('venue')
    date = data.get('date')
    time = data.get('time')

    if not application_id or not status:
        return jsonify({"success": False, "message": "application_id and status required"}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if status.lower() == "approved":
            if not venue or not date or not time:
                return jsonify({"success": False, "message": "Venue, date, and time required for approval"}), 400
            cursor.execute("""
                UPDATE submissions
                SET status=%s, venue=%s, audition_date=%s, audition_time=%s
                WHERE id=%s
            """, (status, venue, date, time, application_id))
        else:
            cursor.execute("""
                UPDATE submissions
                SET status=%s
                WHERE id=%s
            """, (status, application_id))

        conn.commit()
        cursor.execute("SELECT participant_email FROM submissions WHERE id=%s", (application_id,))
        participant_email = cursor.fetchone()["participant_email"]
        send_result_email(participant_email, status, venue, date, time)
        cursor.close()
        conn.close()
        return jsonify({"success": True, "message": "Result updated and email sent"})
    except Exception as e:
        print(traceback.format_exc())
        return jsonify({"success": False, "message": str(e)}), 500

# ---------- MAIN ----------
import os
if __name__ == "__main__":
    # Use Render port if available
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
