from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
import os

app = Flask(__name__)
CORS(app)

# ---------------- CONFIG ---------------- #

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ---------------- DATABASE CONNECTION ---------------- #

def get_db_connection():
    return psycopg2.connect(
        host="localhost",
        database="auditions_db",
        user="postgres",
        password="1234",
        port="5433"
    )

# ---------------- HOME ROUTE ---------------- #

@app.route("/")
def home():
    return "Backend is running successfully"

# ---------------- USER REGISTER ---------------- #

@app.route("/register", methods=["POST"])
def register():
    try:
        data = request.json

        full_name = data.get("fullName")
        age = data.get("age")
        gender = data.get("gender")
        email = data.get("email")
        password = data.get("password")

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO participants (full_name, age, gender, email, password)
            VALUES (%s, %s, %s, %s, %s)
        """, (full_name, age, gender, email, password))

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"success": True, "message": "Registration successful"})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

# ---------------- USER LOGIN ---------------- #

@app.route("/login", methods=["POST"])
def login():
    try:
        data = request.json
        email = data.get("email")
        password = data.get("password")

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT participant_id, full_name
            FROM participants
            WHERE email=%s AND password=%s
        """, (email, password))

        user = cur.fetchone()

        cur.close()
        conn.close()

        if user:
            return jsonify({
                "success": True,
                "participant_id": user[0],
                "full_name": user[1]
            })
        else:
            return jsonify({"success": False, "message": "Invalid email or password"})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

# ---------------- GET AUDITIONS ---------------- #

@app.route("/auditions", methods=["GET"])
def get_auditions():
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT audition_id, title, description, audition_date, location
            FROM auditions
            ORDER BY audition_date ASC
        """)

        rows = cur.fetchall()
        cur.close()
        conn.close()

        audition_list = []

        for row in rows:
            audition_list.append({
                "id": row[0],
                "title": row[1],
                "description": row[2],
                "audition_date": row[3].strftime("%Y-%m-%d") if row[3] else "",
                "location": row[4]
            })

        return jsonify({
            "success": True,
            "auditions": audition_list
        })

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

# ---------------- SUBMIT AUDITION (VIDEO UPLOAD) ---------------- #

@app.route("/submit_audition", methods=["POST"])
def submit_audition():
    try:
        participant_id = request.form.get("participant_id")
        audition_id = request.form.get("audition_id")
        talent_category = request.form.get("talent_category")
        video = request.files.get("video")

        if not video:
            return jsonify({"success": False, "message": "No video uploaded"})

        file_path = os.path.join(UPLOAD_FOLDER, video.filename)
        video.save(file_path)

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO applications
            (participant_id, audition_id, role_applied, video_path, status)
            VALUES (%s, %s, %s, %s, %s)
        """, (participant_id, audition_id, talent_category, file_path, "Pending"))

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            "success": True,
            "message": "Audition submitted successfully"
        })

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

# ---------------- ADMIN REGISTER ---------------- #

@app.route("/admin_register", methods=["POST"])
def admin_register():
    try:
        data = request.json

        full_name = data.get("full_name")
        email = data.get("email")
        password = data.get("password")

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO admins (full_name, email, password)
            VALUES (%s, %s, %s)
        """, (full_name, email, password))

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"success": True, "message": "Admin registered successfully"})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

# ---------------- ADMIN LOGIN ---------------- #

@app.route("/admin_login", methods=["POST"])
def admin_login():
    try:
        data = request.json

        email = data.get("email")
        password = data.get("password")

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT admin_id, full_name
            FROM admins
            WHERE email=%s AND password=%s
        """, (email, password))

        admin = cur.fetchone()

        cur.close()
        conn.close()

        if admin:
            return jsonify({
                "success": True,
                "admin_id": admin[0],
                "full_name": admin[1]
            })
        else:
            return jsonify({"success": False, "message": "Invalid email or password"})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

# ---------------- GET APPLICATIONS FOR ADMIN ---------------- #

@app.route("/admin/applications/<int:audition_id>", methods=["GET"])
def get_applications(audition_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT a.application_id, p.full_name, a.role_applied, a.status
            FROM applications a
            JOIN participants p ON a.participant_id = p.participant_id
            WHERE a.audition_id = %s
        """, (audition_id,))

        rows = cur.fetchall()
        cur.close()
        conn.close()

        result = []

        for row in rows:
            result.append({
                "application_id": row[0],
                "full_name": row[1],
                "talent": row[2],
                "status": row[3]
            })

        return jsonify(result)

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

# ---------------- MARK RESULT ---------------- #

@app.route("/admin/mark_result", methods=["POST"])
def mark_result():
    try:
        data = request.json
        application_id = data.get("application_id")
        status = data.get("status")

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            UPDATE applications
            SET status = %s
            WHERE application_id = %s
        """, (status, application_id))

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"success": True, "message": "Result updated"})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

# ---------------- RUN SERVER ---------------- #

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
