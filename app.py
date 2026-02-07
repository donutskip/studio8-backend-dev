
import os
import sqlite3
from datetime import datetime
from flask import Flask, request, jsonify, session
from flask_cors import CORS
from werkzeug.utils import secure_filename
import json
import time
from flask import send_from_directory, abort
from werkzeug.security import generate_password_hash, check_password_hash
from flask import send_from_directory
from flask import make_response
from werkzeug.middleware.proxy_fix import ProxyFix
import secrets


# -------------------
# App setup
# -------------------
app = Flask(__name__)
app.secret_key = "change-this-secret-in-prod"
app.wsgi_app = ProxyFix(
    app.wsgi_app,
    x_proto=1,
    x_host=1
)

# Required for WP ↔ Flask cookies
app.config.update(
    SESSION_COOKIE_NAME="studio8_session",
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
)

CORS(
    app,
    supports_credentials=True,
    origins=[
        "https://wp.studio8maf.com",
        "https://studio8maf.com",
	"https://dev-api.studio8maf.com"
    ]
)

# -------------------
# Paths / Config
# -------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = "/home/ubuntu/studio8-backend/studio8.db"
UPLOAD_DIR = "/home/ubuntu/studio8-backend/uploads"

os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "pdf"}

# -------------------
# Helpers
# -------------------
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def is_admin():
    return session.get("is_admin") is True

# ===================
# ADMIN READ-ONLY APIs
# ===================

@app.route("/admin/training-logins", methods=["GET"])
def admin_training_logins():
    if not is_admin():
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            tl.id,
            c.client_code,
            c.full_name,
            tl.service_id,
            tl.proof_filename,
            tl.logged_at
        FROM training_logins tl
        JOIN clients c ON c.id = tl.client_id
        ORDER BY tl.logged_at DESC
    """)

    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return jsonify(rows)


@app.route("/admin/membership-payments", methods=["GET"])
def admin_membership_payments():
    if not is_admin():
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            mp.id,
            c.client_code,
            c.full_name,
            mp.proof_filename,
            mp.logged_at
        FROM membership_payments mp
        JOIN clients c ON c.id = mp.client_id
        ORDER BY mp.logged_at DESC
    """)

    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return jsonify(rows)


@app.route("/admin/payments", methods=["GET"])
def admin_payments():
    if not is_admin():
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM payments
        ORDER BY created_at DESC
    """)

    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return jsonify(rows)

# expose uploads
@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    if not is_admin():
        return jsonify({"error": "Unauthorized"}), 401
    return send_from_directory(UPLOAD_DIR, filename)


# -------------------
# Health check
# -------------------
@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "service": "studio8-backend",
        "time": datetime.utcnow().isoformat()
    })

# Admin Login Page
@app.route("/admin/login-page", methods=["GET"])
def admin_login_page():
    return send_from_directory("admin_ui", "login.html")

# Admin home page
@app.route("/admin")
def admin_home():
    if not session.get("is_admin"):
        return jsonify({"error": "Unauthorized"}), 401

    return send_from_directory("admin_ui", "index.html")

# Admin login API
@app.route("/admin/login", methods=["POST"])
def admin_login():
    data = request.get_json(force=True)
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "Missing credentials"}), 400

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, password_hash, failed_attempts, locked_until
        FROM admins
        WHERE username = ?
    """, (username,))
    admin = cur.fetchone()

    if not admin:
        return jsonify({"error": "Invalid credentials"}), 401

    if admin["locked_until"]:
        locked_until = datetime.fromisoformat(admin["locked_until"])
        if datetime.utcnow() < locked_until:
            return jsonify({"error": "Account locked"}), 403

    if not check_password_hash(admin["password_hash"], password):
        cur.execute("""
            UPDATE admins
            SET failed_attempts = failed_attempts + 1
            WHERE id = ?
        """, (admin["id"],))
        conn.commit()
        return jsonify({"error": "Invalid credentials"}), 401

    # success
    cur.execute("""
        UPDATE admins
        SET failed_attempts = 0, locked_until = NULL
        WHERE id = ?
    """, (admin["id"],))
    conn.commit()
    conn.close()

    session.clear()
    session["is_admin"] = True
    session["admin_id"] = admin["id"]

    return jsonify({"success": True})

# Admin training Logs
@app.route("/admin/training-logs")
def admin_training_logs_page():
    if not session.get("is_admin"):
        return jsonify({"error": "Unauthorized"}), 401

    return send_from_directory("admin_ui", "dashboard.html")

# Admin Clients
@app.route("/admin/clients")
def admin_clients_page():
    if not session.get("is_admin"):
        return jsonify({"error": "Unauthorized"}), 401

    return send_from_directory("admin_ui", "clients.html")

# Admin Clients Info
@app.route("/admin/clients-info", methods=["GET"])
def admin_clients_info():
    if not is_admin():
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT client_code, full_name, status, created_at
        FROM clients
        ORDER BY created_at DESC
    """)

    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return jsonify(rows)



# Admin logout
@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.clear()
    return jsonify({"success": True})


# Admin Session Checkpoint
@app.route("/admin/me", methods=["GET"])
def admin_me():
    if not session.get("is_admin"):
        return jsonify({"authenticated": False}), 401

    return jsonify({
        "authenticated": True,
        "admin_id": session.get("admin_id")
    })


# -------------------
# Registration
# -------------------
@app.route("/register", methods=["POST"])
def register():
    try:
        data = request.get_json(force=True)

        required = [
            "client_code", "pin", "full_name",
            "consent_health", "consent_privacy"
        ]

        for field in required:
            if field not in data or not data[field]:
                return jsonify({"error": f"Missing field: {field}"}), 400

        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO clients (
                client_code,
                pin_hash,
                full_name,
                email,
                phone,
                emergency_name,
                emergency_phone,
                medical_notes,
                consent_health,
                consent_privacy,
	        status,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data["client_code"],
            data["pin"],
            data["full_name"],
            data.get("email"),
            data.get("phone"),
            data.get("emergency_name"),
            data.get("emergency_phone"),
            data.get("medical_notes"),
            int(data["consent_health"]),
            int(data["consent_privacy"]),
	    "NON_MEMBER",
            datetime.utcnow().isoformat()
        ))

        conn.commit()
        conn.close()

        # ✅ THIS IS THE MOST IMPORTANT LINE
        return jsonify({"success": True}), 201

    except sqlite3.IntegrityError:
        return jsonify({"error": "Client code already exists"}), 409

    except Exception as e:
        print("REGISTER ERROR:", e)
        return jsonify({"error": "Internal server error"}), 500

# -------------------
# Admin: Promote client to MEMBER
# -------------------
@app.route("/admin/clients/<int:client_id>/approve", methods=["POST"])
def approve_client(client_id):
    if not session.get("is_admin"):
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE clients
        SET status = 'MEMBER'
        WHERE id = ?
    """, (client_id,))

    if cur.rowcount == 0:
        conn.close()
        return jsonify({"error": "Client not found"}), 404

    conn.commit()
    conn.close()

    return jsonify({"success": True})


# /admin/clients-info must include id
@app.route("/admin/clients-info")
def admin_clients_info():
    if not session.get("is_admin"):
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, client_code, full_name, status, created_at
        FROM clients
        ORDER BY created_at DESC
    """)
    rows = cur.fetchall()
    conn.close()

    return jsonify([dict(row) for row in rows])





# -------------------
# Client dropdown
# -------------------
@app.route("/clients", methods=["GET"])
def get_clients():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT client_code FROM clients ORDER BY client_code ASC")
    rows = cur.fetchall()
    conn.close()

    return jsonify([row["client_code"] for row in rows])

# -------------------
# Login
# -------------------
@app.route("/login", methods=["POST"])
def login():
    data = request.json or {}
    client_code = data.get("client_code")
    pin = data.get("pin")

    if not client_code or not pin:
        return jsonify({"valid": False}), 400

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, full_name, pin_hash, status
        FROM clients
        WHERE client_code = ?
    """, (client_code,))
    client = cur.fetchone()

    if not client or client["pin_hash"] != pin:
        conn.close()
        return jsonify({"valid": False}), 401

    session.clear()
    session["client_id"] = client["id"]

    cur.execute("""
        INSERT INTO sessions (client_id, action, created_at)
        VALUES (?, 'LOGIN', datetime('now','localtime'))
    """, (client["id"],))

    conn.commit()
    conn.close()


    return jsonify({
        "valid": True,
        "full_name": client["full_name"],
        "status": client["status"]
    })

# -------------------
# Current session
# -------------------
@app.route("/me", methods=["GET"])
def me():
    token = request.headers.get("X-Auth-Token")
    client_id = session.get("client_id")
    if not client_id:
        return jsonify({"error": "Not authenticated"}), 401

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT full_name, status
        FROM clients
        WHERE id = ?
    """, (client_id,))
    client = cur.fetchone()
    conn.close()

    if not client:
        session.clear()
        return jsonify({"error": "Invalid session"}), 401

    return jsonify({
        "full_name": client["full_name"],
        "status": client["status"]
    })

# -------------------
# TRAINING LOGIN (FIXED + ENHANCED)
# -------------------
@app.route("/training/login", methods=["POST"])
def training_login():
    client_id = session.get("client_id")
    if not client_id:
    	return jsonify({"success": False, "error": "Not authenticated"}), 401

    if not client_id:
    	return jsonify({"success": False, "error": "Not authenticated"}), 401

    service_id = request.form.get("service_id")
    proof = request.files.get("proof")

    if not service_id:
        return jsonify({"success": False, "error": "Service not selected"}), 400

    if not proof or proof.filename == "":
        return jsonify({"success": False, "error": "Proof required"}), 400

    if not allowed_file(proof.filename):
        return jsonify({"success": False, "error": "Invalid file type"}), 400

    # Get client details for filename
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT client_code, full_name FROM clients WHERE id = ?", (client_id,))
    client = cur.fetchone()

    if not client:
        conn.close()
        return jsonify({"success": False, "error": "Client not found"}), 400

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = proof.filename.rsplit(".", 1)[1].lower()

    filename = secure_filename(
        f"session_{client['client_code']}_{client['full_name'].replace(' ', '_')}_{ts}.{ext}"
    )

    file_path = os.path.join(UPLOAD_DIR, filename)
    proof.save(file_path)

    # ✅ CORRECT columns
    logged_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cur.execute("""
    INSERT INTO training_logins (
        client_id,
        service_id,
        proof_filename,
        logged_at
    )
    VALUES (?, ?, ?, ?)
    """, (
    client_id,
    service_id,
    filename,
    logged_at
    ))


    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": "Training login recorded"
    })


#--------------------
# Membership Payments Upload
#--------------------
@app.route("/membership/upload", methods=["POST"])
def upload_membership_payment():
    client_id = session.get("client_id")
    if not client_id:
    	return jsonify({"success": False, "error": "Not authenticated"}), 401

    if not client_id:
    	return jsonify({"success": False, "error": "Not authenticated"}), 401
    proof = request.files.get("proof")
    if not proof or proof.filename == "":
        return jsonify({"success": False, "error": "Proof required"}), 400

    if not allowed_file(proof.filename):
        return jsonify({"success": False, "error": "Invalid file type"}), 400

    # Get client info for filename
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT client_code, full_name FROM clients WHERE id = ?", (client_id,))
    client = cur.fetchone()

    if not client:
        conn.close()
        return jsonify({"success": False, "error": "Client not found"}), 400

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = secure_filename(client["full_name"].replace(" ", "_"))

    filename = (
        f"annual_{client['client_code']}_"
        f"{safe_name}_{timestamp}."
        f"{proof.filename.rsplit('.',1)[1]}"
    )

    proof.save(os.path.join(UPLOAD_DIR, filename))

    cur.execute("""
        INSERT INTO membership_payments (
            client_id,
            proof_filename,
            logged_at
        )
        VALUES (?, ?, ?)
    """, (
        client_id,
        filename,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": "Membership payment uploaded"
    })


# -------------------
# Logout
# -------------------
@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"success": True})

# -------------------
# Run
# -------------------
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5101, debug=False)
