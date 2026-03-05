"""
NightGuard V2 — Web API (Flask)
Start: gunicorn main:app --bind 0.0.0.0:10000
"""
import os, sys, threading
from pathlib import Path

# Fix: ensure all engine files are importable
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

# Fix relative imports in subpackages
import importlib, types

def _fix_relative_imports():
    """
    Patch parser.py và các file khác nếu chúng dùng relative import.
    Đọc source, thay 'from .lexer' -> 'from lexer', load lại.
    """
    files_to_patch = [
        os.path.join(BASE, "parser.py"),
        os.path.join(BASE, "lexer.py"),
    ]
    for fpath in files_to_patch:
        if not os.path.exists(fpath): continue
        with open(fpath, "r") as f:
            src = f.read()
        # replace relative imports
        patched = src.replace("from .lexer ", "from lexer ") \
                     .replace("from .parser ", "from parser ") \
                     .replace("from .ast_nodes ", "from ast_nodes ")
        if patched != src:
            with open(fpath, "w") as f:
                f.write(patched)
            print(f"[patch] Fixed relative imports in {os.path.basename(fpath)}")

_fix_relative_imports()

from flask import Flask, request, jsonify, send_from_directory
from cli import obfuscate

app = Flask(__name__, static_folder="static")

MAX_BYTES = 1_000_000  # 1 MB

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
        return jsonify({"error": "Script too large (max 1 MB)"}), 413

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
        return jsonify({"error": msg}), (400 if kind == "lua_error" else 500)

    result = result_box[0]
    return jsonify({
        "result":       result,
        "input_bytes":  len(code.encode()),
        "output_bytes": len(result.encode()),
    })

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory("static", filename)

@app.route("/")
def index():
    return send_from_directory("static", "index.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
