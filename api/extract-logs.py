import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, jsonify, request

from _lib.log_extraction import extract_logs

app = Flask(__name__)


@app.route("/api/extract-logs", methods=["POST"])
def handle_extract_logs():
    uploaded_files = request.files.getlist("files")
    if not uploaded_files:
        return jsonify({"ok": False, "error": "Missing 'files' in form data"}), 400

    files = [(f.filename or "unnamed", f.read()) for f in uploaded_files]

    format = request.form.get("format", "auto")
    tz = request.form.get("tz", "America/Sao_Paulo")
    result = extract_logs(files, format=format, tz=tz)
    status = 200 if result["ok"] else 400
    return jsonify(result), status
