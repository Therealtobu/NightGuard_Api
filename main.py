"""
NightGuard V2 — Web API (Flask)
Start: gunicorn main:app --bind 0.0.0.0:10000
"""
import os, sys, json, threading
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cli import obfuscate

app = Flask(__name__, static_folder="static")

MAX_BYTES = 1_000_000  # 512 KB

# ── CORS ──────────────────────────────────────────────────────────────
@app.after_request
def cors(resp):
    resp.headers["Access-Control-Allow-Origin"]  = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return resp

# ── API ───────────────────────────────────────────────────────────────
@app.route("/obfuscate", methods=["POST", "OPTIONS"])
def api_obfuscate():
    if request.method == "OPTIONS":
        return "", 204

    try:
        body = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "Invalid JSON"}), 400

    code = (body or {}).get("code", "").strip()
    seed = (body or {}).get("seed", None)

    if not code:
        return jsonify({"error": "code is empty"}), 400
    if len(code.encode()) > MAX_BYTES:
        return jsonify({"error": "Script too large (max 512 KB)"}), 413

    # Run with timeout via thread
    result_box = [None]
    error_box  = [None]

    def run():
        try:
            result_box[0] = obfuscate(code, seed)
        except SyntaxError as e:
            error_box[0] = ("lua_error", str(e))
        except Exception as e:
            error_box[0] = ("error", str(e))

    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(timeout=60)

    if t.is_alive():
        return jsonify({"error": "Timed out — try a smaller script"}), 504
    if error_box[0]:
        kind, msg = error_box[0]
        code_map = {"lua_error": 400, "error": 500}
        return jsonify({"error": msg}), code_map.get(kind, 500)

    result = result_box[0]
    return jsonify({
        "result":       result,
        "input_bytes":  len(code.encode()),
        "output_bytes": len(result.encode()),
    })

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

# ── Static + index ────────────────────────────────────────────────────
@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory("static", filename)

@app.route("/")
def index():
    return send_from_directory("static", "index.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
