import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, jsonify, request

from _lib.extraction import extract_map

app = Flask(__name__)


@app.route("/api/extract-map", methods=["POST"])
def handle_extract_map():
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "Missing 'file' in form data"}), 400

    uploaded = request.files["file"]
    svg_bytes = uploaded.read()
    if not svg_bytes:
        return jsonify({"ok": False, "error": "Uploaded file is empty"}), 400

    mode = request.form.get("mode", "card")
    result = extract_map(svg_bytes, mode=mode)
    status = 200 if result["ok"] else 400
    return jsonify(result), status
