"""Online (server-based) license activation for Bangla VoiceTyper.

Used when the developer has deployed the license server and set
``license.server`` in the config. When no server is configured the app
keeps working with the offline checksum check for backwards compatibility.

The server keeps an allow-list of registered keys and binds each key to the
first device that activates it, so one key works on one computer only.
Network problems use a 7-day offline grace so a buyer is never locked out
just because their internet is temporarily down.
"""

import hashlib
import json
import platform
import socket
import urllib.error
import urllib.request

FALLBACK_SERVER = ""
GRACE_DAYS = 7


def server_url(settings) -> str:
    """Return the configured license server URL ('' means offline mode)."""
    url = (settings.get("license", "server", "") or "").strip().rstrip("/")
    return url


def is_online(settings) -> bool:
    """True if online activation is configured."""
    return bool(server_url(settings))


def get_device_id() -> str:
    """Return a stable per-computer id (built once from Windows MachineGuid).

    Deterministic: the same machine always returns the same id, and it does
    not change across app restarts. No personal data leaves the machine.
    """
    base = ""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography"
        )
        value, _ = winreg.QueryValueEx(key, "MachineGuid")
        base = str(value)
    except Exception:
        base = platform.node() or socket.gethostname() or "unknown-machine"
    digest = hashlib.sha256(("BVT-device::" + base).encode("utf-8")).hexdigest()
    return digest[:32].upper()


def _post(url: str, payload: dict, timeout: int = 8):
    """POST JSON, return (status_code, json) or raise on network error."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


def activate(settings, key: str):
    """Try to activate ``key`` for this device via the server.

    Returns a dict like {"ok": bool, "message": str} ready to show the user.
    """
    url = server_url(settings)
    if not url:
        return {"ok": False, "message": "যাচাই-সার্ভার সেট আপ করা হয়নি।"}
    try:
        status, result = _post(
            url + "/activate", {"key": key, "device_id": get_device_id()}
        )
    except urllib.error.HTTPError as exc:
        if exc.code == 402:
            return {"ok": False,
                    "message": "এই key-টি এখনো নিবন্ধিত নয়। সঠিক key সংগ্রহের জন্য "
                               "ডেভলপারের সাথে যোগাযোগ করুন।"}
        if exc.code == 403:
            return {"ok": False,
                    "message": "এই key অন্য একটি কম্পিউটারে ব্যবহার হয়ে গেছে। "
                               "নতুন key-এর জন্য ডেভলপারের সাথে যোগাযোগ করুন।"}
        if exc.code == 401:
            return {"ok": False, "message": "key টি বৈধ নয়।"}
        return {"ok": False, "message": f"সার্ভারের সমস্যা ({exc.code})। পরে আবার চেষ্টা করুন।"}
    except urllib.error.URLError:
        return {"ok": False,
                "message": "যাচাই-সার্ভারে যোগাযোগ করা যায়নি। ইন্টারনেট বা "
                           "সার্ভার ঠিক আছে কিনা দেখুন।"}
    except Exception:
        return {"ok": False, "message": "যাচাই-এর সময় সমস্যা হয়েছে। পরে আবার চেষ্টা করুন।"}

    if status == 200 and result.get("status") == "ok":
        return {"ok": True, "message": result.get("message", "সক্রিয় হয়েছে।")}
    return {"ok": False, "message": result.get("message", "সক্রিয় করা যায়নি।")}


def verify(settings, key: str):
    """Server-side check: is this key bound to this device right now?

    Returns dict {"ok": bool, "reachable": bool, "message": str}.
    ``reachable`` is False on network/server failure.
    """
    url = server_url(settings)
    if not url:
        return {"ok": False, "reachable": False, "message": "কোনো সার্ভার কনফিগার হয়নি।"}
    try:
        status, result = _post(url + "/verify", {"key": key, "device_id": get_device_id()})
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return {"ok": False, "reachable": True,
                    "message": "লাইসেন্স এই কম্পিউটারে বৈধ নয়।"}
        return {"ok": False, "reachable": True,
                "message": f"সার্ভারের সমস্যা ({exc.code})।"}
    except urllib.error.URLError:
        return {"ok": False, "reachable": False,
                "message": "যাচাই-সার্ভারে যোগাযোগ করা যায়নি।"}
    except Exception:
        return {"ok": False, "reachable": False, "message": "যাচাই-এ সমস্যা হয়েছে।"}

    if status == 200 and result.get("status") == "ok":
        return {"ok": True, "reachable": True, "message": "লাইসেন্স বৈধ।"}
    return {"ok": False, "reachable": True, "message": "লাইসেন্স বৈধ নয়।"}


def within_grace(settings) -> bool:
    """True if the last verified timestamp is recent enough for offline use."""
    import datetime
    raw = (settings.get("license", "last_verified", "") or "").strip()
    if not raw:
        return False
    try:
        last = datetime.date.fromisoformat(raw)
    except ValueError:
        return False
    return (datetime.date.today() - last).days <= GRACE_DAYS