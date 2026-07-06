import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, jsonify, request

from _lib.matching import run_matching

app = Flask(__name__)


@app.route("/api/match", methods=["POST"])
def handle_match():
    if "spec" not in request.files or "logs" not in request.files:
        return jsonify({"ok": False, "error": "Both 'spec' and 'logs' files are required"}), 400

    spec = request.files["spec"]
    logs = request.files["logs"]
    spec_content = spec.read()
    logs_content = logs.read()
    if not spec_content:
        return jsonify({"ok": False, "error": "The spec file is empty"}), 400

    result = run_matching(
        (spec.filename or "spec", spec_content),
        (logs.filename or "logs", logs_content),
    )
    status = 200 if result["ok"] else 400
    return jsonify(result), status
