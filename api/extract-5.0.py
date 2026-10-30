import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, jsonify, request

from _lib.extraction import extract_map
from _lib.map5_extraction import extract_cards_5_0, reparse_5_0

app = Flask(__name__)


@app.route("/api/extract-5.0", methods=["POST"])
def handle_extract_5_0():
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "Missing 'file' in form data"}), 400
    content = request.files["file"].read()
    if not content:
        return jsonify({"ok": False, "error": "Uploaded file is empty"}), 400
    # Primary: read cards from the SVG's shape structure (exact per-card text). Fall back to
    # the base parser + bbox re-parse for exports without Whimsical's content groups.
    try:
        events = extract_cards_5_0(content)
    except ValueError:
        events = []
    if events:
        return jsonify({"ok": True, "events": events}), 200
    base = extract_map(content, mode="card")
    if not base.get("ok"):
        return jsonify({"ok": False, "error": base.get("error", "Failed to parse SVG")}), 400
    try:
        events = reparse_5_0(base["spec"], base.get("lines"))
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    return jsonify({"ok": True, "events": events}), 200
