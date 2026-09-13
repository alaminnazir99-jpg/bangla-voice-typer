"""License key generation and validation for Bangla VoiceTyper.

Keys look like: XXXX-XXXX-XXXX-XXXX using an unambiguous alphabet
(no 0/O/1/I). The final two characters are a checksum derived from the
payload plus a secret, so random/copied keys are rejected and new keys
can only be issued by the generator (the seller).
"""

import hashlib

APP_SECRET = "BVT-LIC-2026-9f3a7c1e"
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_CHAR_TO_VAL = {c: i for i, c in enumerate(ALPHABET)}


def _checksum(payload: str) -> str:
    digest = hashlib.sha256(
        (APP_SECRET + "::" + payload).encode("utf-8")
    ).digest()
    a = digest[0] % len(ALPHABET)
    b = digest[1] % len(ALPHABET)
    return ALPHABET[a] + ALPHABET[b]


def generate_keys(count: int = 1) -> list:
    """Generate ``count`` fresh license keys (list of formatted strings)."""
    import secrets

    keys = []
    while len(keys) < count:
        payload = "".join(secrets.choice(ALPHABET) for _ in range(14))
        raw = payload + _checksum(payload)
        keys.append(format_key(raw))
    return keys


def normalize(key: str) -> str:
    """Strip spaces/dashes and uppercase a key."""
    return "".join(ch for ch in str(key).upper() if ch.isalnum())


def validate(key: str) -> bool:
    """Return True if ``key`` is a valid Bangla VoiceTyper license key."""
    cleaned = normalize(key)
    if len(cleaned) != 16:
        return False
    if any(ch not in _CHAR_TO_VAL for ch in cleaned):
        return False
    payload = cleaned[:14]
    check = cleaned[14:]
    return _checksum(payload) == check


def format_key(key: str) -> str:
    """Return a key in the XXXXX-XXXX-XXXX-XXXX display format."""
    cleaned = normalize(key)
    return "-".join(cleaned[i:i + 4] for i in range(0, len(cleaned), 4))