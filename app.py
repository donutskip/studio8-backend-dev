import os
import sqlite3
from datetime import datetime
from flask import Flask, request, jsonify, session
from flask_cors import CORS
from werkzeug.utils import secure_filename
import json

# -------------------
# App setup
# -------------------
app = Flask(__name__)
app.secret_key = "change-this-secret-in-prod"

# Required for WP ↔ Flask cookies
app.config.update(
    SESSION_COOKIE_SAMESITE="None",
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True
)

CORS(
    app,
    supports_credentials=True,
    origins=[
        "https://wp.studio8maf.com",
        "https://studio8maf.com"
    ]
)

# -------------------
# Paths / Config
# -------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "studio8.db")

UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
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

# -------------------
# Registration
# -------------------
@app.route("/register", methods=["POST"])
def register():
    print("RAW PAYLOAD:")
    print(json.dumps(request.json, indent=2))
    data = request.json

    if not data:
        return jsonify({"error": "Invalid payload"}), 400

    # TEMP: log payload for verification
    print("FORMINATOR PAYLOAD:", data)

    return jsonify({
        "success": True,
        "message": "Webhook received"
    }), 200


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
    app.run(host="0.0.0.0", port=5001, debug=True)
