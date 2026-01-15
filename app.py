from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
from datetime import datetime

app = Flask(__name__)
CORS(app)  # Allow WordPress / browser calls

DB_PATH = "studio8.db"


# ---------- Database Helper ----------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ---------- Health Check ----------
@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "service": "studio8-backend",
        "time": datetime.utcnow().isoformat()
    })


# ---------- Login Endpoint ----------
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

    db = get_db()
    cur = db.cursor()

    cur.execute("""
        SELECT id, pin_hash, status
        FROM clients
        WHERE client_code = ?
    """, (client_code,))

    client = cur.fetchone()

    if not client:
        db.close()
        return jsonify({
            "valid": False,
            "status": "DENIED"
        }), 401

    if client["pin_hash"] != pin:
        db.close()
        return jsonify({
            "valid": False,
            "status": "DENIED"
        }), 401

    # Optional: log session (Phase 3 ready)
    cur.execute("""
        INSERT INTO sessions (client_id, service)
        VALUES (?, ?)
    """, (client["id"], "LOGIN"))

    db.commit()
    db.close()

    return jsonify({
        "valid": True,
        "status": client["status"],
        "notes": "Manual verification pending"
    })


# ---------- Run ----------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
