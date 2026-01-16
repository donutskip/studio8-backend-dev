import sqlite3
from datetime import datetime
from flask import Flask, request, jsonify, session
from flask_cors import CORS

# -------------------
# App setup
# -------------------
app = Flask(__name__)
app.secret_key = "change-this-secret-in-prod"

# REQUIRED for cross-domain cookies (WordPress → Flask)
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

DB_PATH = "studio8.db"

# -------------------
# DB helper
# -------------------
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
# Client codes (dropdown)
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
        return jsonify({"valid": False, "error": "Missing credentials"}), 400

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
        return jsonify({"valid": False, "status": "DENIED"}), 401

    # ---- Persist session ----
    session.clear()
    session["client_id"] = client["id"]

    # ---- Capture metadata ----
    ip_address = request.headers.get("X-Forwarded-For", request.remote_addr)
    user_agent = request.headers.get("User-Agent", "unknown")

    # ---- Log login (ALWAYS) ----
    cur.execute("""
        INSERT INTO sessions (
            client_id,
            action,
            ip_address,
            user_agent,
            created_at
        )
        VALUES (?, 'LOGIN', ?, ?, datetime('now','localtime'))
    """, (
        client["id"],
        ip_address,
        user_agent
    ))

    conn.commit()
    conn.close()

    return jsonify({
        "valid": True,
        "full_name": client["full_name"],
        "status": client["status"]   # MEMBER / NON_MEMBER
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
        return jsonify({"error": "Session invalid"}), 401

    return jsonify({
        "full_name": client["full_name"],
        "status": client["status"]
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
