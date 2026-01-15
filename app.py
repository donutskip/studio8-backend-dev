import sqlite3
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app, origins=[
    "https://wp.studio8maf.com",
    "https://studio8maf.com"
])

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
# Get ALL client codes (for dropdown)
# MEMBER and NON_MEMBER both included
# -------------------
@app.route("/clients", methods=["GET"])
def get_clients():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT client_code
        FROM clients
        ORDER BY client_code ASC
    """)

    rows = cur.fetchall()
    conn.close()

    return jsonify([row["client_code"] for row in rows])


# -------------------
# Login endpoint
# MEMBER and NON_MEMBER both allowed
# -------------------
@app.route("/login", methods=["POST"])
def login():
    data = request.json or {}
    client_code = data.get("client_code")
    pin = data.get("pin")

    if not client_code or not pin:
        return jsonify({
            "valid": False,
            "error": "Missing client_code or pin"
        }), 400

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, pin_hash, status
        FROM clients
        WHERE client_code = ?
    """, (client_code,))

    client = cur.fetchone()

    if not client or client["pin_hash"] != pin:
        conn.close()
        return jsonify({
            "valid": False,
            "status": "DENIED"
        }), 401

    # Log session
    cur.execute("""
        INSERT INTO sessions (client_id, service)
        VALUES (?, ?)
    """, (client["id"], "LOGIN"))

    conn.commit()
    conn.close()

    return jsonify({
        "valid": True,
        "membership_type": client["status"],  # MEMBER | NON_MEMBER
        "notes": "Login successful"
    })


# -------------------
# Run app (dev only)
# -------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
