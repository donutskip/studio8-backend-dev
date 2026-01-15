from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__)
CORS(app)  # allow WordPress / browser calls

# --- TEMP IN-MEMORY STORE (Phase 3) ---
# Later this becomes SQLite / MySQL
CLIENTS = {
    "test": {
        "pin": "1234",
        "status": "ACTIVE",
        "verified": False
    }
}

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "service": "studio8-backend",
        "time": datetime.utcnow().isoformat()
    })

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

    client = CLIENTS.get(client_code)

    if not client or client["pin"] != pin:
        return jsonify({
            "valid": False,
            "status": "DENIED"
        }), 401

    return jsonify({
        "valid": True,
        "status": client["status"],
        "notes": "Manual verification pending"
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
