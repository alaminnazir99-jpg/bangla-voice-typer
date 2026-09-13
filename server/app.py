"""Flask license server for Bangla VoiceTyper online activation.

Deploy this on any Flask host (e.g. PythonAnywhere free tier).

The server keeps an explicit allow-list of keys the developer generated
(added via /add_keys). Only keys in that list can activate, and every key
binds to the FIRST device that activates it - so one key = one computer.
Everything else (checksum-valid keys that were never uploaded, copied keys
on a different machine) is rejected.

Storage: keys.json next to this file.
Admin token: set env var ADMIN_TOKEN (do NOT commit a real token).
"""

import json
import os
import threading

from flask import Flask, jsonify, request

app = Flask(__name__)

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "keys.json")
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "change-me")
MAX_DEVICES_PER_KEY = 1

# Same alphabet/checksum scheme as the app (core/license.py).
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _lock() -> threading.Lock:
    return threading.Lock()


_store_lock = _lock()


def _checksum_ok(key: str) -> bool:
    """Validate checksum (mirror of core.license.validate, kept here so the
    server needs no app dependency)."""
    cleaned = "".join(ch for ch in str(key).upper() if ch.isalnum())
    if len(cleaned) != 16:
        return False
    if any(ch not in ALPHABET for ch in cleaned):
        return False
    secret = "BVT-LIC-2026-9f3a7c1e"
    import hashlib
    digest = hashlib.sha256(
        (secret + "::" + cleaned[:14]).encode("utf-8")
    ).digest()
    a = digest[0] % len(ALPHABET)
    b = digest[1] % len(ALPHABET)
    return ALPHABET[a] + ALPHABET[b] == cleaned[14:]


def _load() -> dict:
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _save(data: dict) -> None:
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, DATA_FILE)


def _get_keys() -> dict:
    with _store_lock:
        return _load()


def _update_keys(mutator) -> None:
    with _store_lock:
        data = _load()
        mutator(data)
        _save(data)


def _norm_key(key: str) -> str:
    cleaned = "".join(ch for ch in str(key).upper() if ch.isalnum())
    return "-".join(cleaned[i:i + 4] for i in range(0, len(cleaned), 4))


@app.route("/activate", methods=["POST"])
def activate():
    body = request.get_json(silent=True) or {}
    raw_key = str(body.get("key", "")).strip()
    device_id = str(body.get("device_id", "")).strip()
    if not raw_key or not device_id:
        return jsonify({"status": "bad_request"}), 400
    if not _checksum_ok(raw_key):
        return jsonify({"status": "invalid"}), 401

    key = _norm_key(raw_key)
    keys = _get_keys()
    if key not in keys:
        # Checksum is fine but the developer never added this key.
        return jsonify({"status": "unknown"}), 402
    rec = keys[key]
    bound = rec.get("device")
    if bound is None:
        _update_keys(lambda d: d.setdefault(key, {}).update(device=device_id))
        return jsonify({"status": "ok", "message": "লাইসেন্স সফলভাবে সক্রিয় হয়েছে।"}), 200
    if bound == device_id:
        return jsonify({"status": "ok", "message": "লাইসেন্স ইতিমধ্যে এই কম্পিউটারে সক্রিয়।"}), 200
    return jsonify({"status": "used", "message": "এই key অন্য একটি কম্পিউটারে ব্যবহার হয়েছে।"}), 403


@app.route("/verify", methods=["POST"])
def verify():
    body = request.get_json(silent=True) or {}
    raw_key = str(body.get("key", "")).strip()
    device_id = str(body.get("device_id", "")).strip()
    key = _norm_key(raw_key)
    rec = _get_keys().get(key)
    if rec is None or rec.get("device") != device_id:
        return jsonify({"status": "no"}), 404
    return jsonify({"status": "ok"}), 200


@app.route("/add_keys", methods=["POST"])
def add_keys():
    body = request.get_json(silent=True) or {}
    token = str(body.get("token", ""))
    if token != ADMIN_TOKEN:
        return jsonify({"status": "forbidden"}), 403
    keys = [str(k).strip() for k in body.get("keys", []) if str(k).strip()]
    valid, added, skipped = [], 0, 0
    for k in keys:
        if _checksum_ok(k):
            valid.append(_norm_key(k))
        else:
            skipped += 1
    def _add(data):
        nonlocal added
        for k in valid:
            if k not in data:
                data[k] = {"device": None}
                added += 1
    _update_keys(_add)
    return jsonify({
        "status": "ok",
        "added": added,
        "already_present": len(valid) - added,
        "skipped_invalid": skipped,
    }), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "app": "BanglaVoiceTyper-license"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)