from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
import traceback
import smtplib
from email.mime.text import MIMEText
import os
from werkzeug.utils import secure_filename

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

    # Replace with your SMTP settings
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

# Participant registration & login
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

# ---------- MORE ROUTES ----------
# Add admin_register, admin_login, post_audition, get_auditions, mark_result, submit_audition, get_submissions
# Keep existing logic, just ensure no debug=True and dynamic port

# ---------- MAIN ----------
@app.route("/ping")
def ping():
    return {"status": "ok"}
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
