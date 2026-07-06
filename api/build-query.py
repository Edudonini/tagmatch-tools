import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, jsonify, request

from _lib.query_building import build_query, parse_spec_file

app = Flask(__name__)


@app.route("/api/build-query", methods=["POST"])
def handle_build_query():
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "Missing 'file' in form data"}), 400

    uploaded = request.files["file"]
    content = uploaded.read()
    if not content:
        return jsonify({"ok": False, "error": "Uploaded file is empty"}), 400

    try:
        events = parse_spec_file(uploaded.filename or "unnamed", content)
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400

    mode = request.form.get("mode", "generate")
    if mode == "parse":
        return jsonify({"ok": True, "events": events}), 200

    query_type = request.form.get("query_type", "")
    try:
        options = json.loads(request.form.get("options", "{}"))
    except json.JSONDecodeError:
        return jsonify({"ok": False, "error": "Malformed 'options' JSON"}), 400

    result = build_query(events, query_type, options)
    status = 200 if result["ok"] else 400
    return jsonify(result), status
