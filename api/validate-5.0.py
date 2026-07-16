import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, jsonify, request

from _lib.extraction import extract_map
from _lib.map5_extraction import reparse_5_0
from _lib.map5_validation import validate_events

app = Flask(__name__)


@app.route("/api/validate-5.0", methods=["POST"])
def handle_validate_5_0():
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "Missing 'file' in form data"}), 400
    content = request.files["file"].read()
    if not content:
        return jsonify({"ok": False, "error": "Uploaded file is empty"}), 400
    base = extract_map(content, mode="card")
    if not base.get("ok"):
        return jsonify({"ok": False, "error": base.get("error", "Failed to parse SVG")}), 400
    try:
        events = reparse_5_0(base["spec"])
        validation = validate_events(events)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    return jsonify({"ok": True, "events": events, "validation": validation}), 200
