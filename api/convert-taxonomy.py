import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, jsonify, request

from _lib.taxonomy5 import convert_events

app = Flask(__name__)


@app.route("/api/convert-taxonomy", methods=["POST"])
def handle_convert():
    payload = request.get_json(force=True, silent=True)
    if not isinstance(payload, dict):
        return jsonify({"ok": False, "error": "Body must be a JSON object."}), 400
    try:
        events = convert_events(payload.get("events"))
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    return jsonify({"ok": True, "events": events}), 200
