"""Register generated license keys on the Bangla VoiceTyper license server.

Run AFTER generating keys with keygen.py so the server knows they are
valid-to-sell. Keys not registered here cannot activate (even if the
checksum is valid), which is what keeps buyers coming to you.

Usage:
    python register_keys.py <SERVER_URL> <ADMIN_TOKEN> KEY1 KEY2 ...

Example:
    python register_keys.py https://yourname.pythonanywhere.com s3cret K4XW-... 3F8H-...
"""
import json
import sys
import urllib.request


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)
    server = sys.argv[1].rstrip("/")
    token = sys.argv[2]
    keys = [k for k in sys.argv[3:] if k.strip()]
    if not keys:
        print("কোনো key দেওয়া হয়নি।")
        sys.exit(1)

    payload = json.dumps({"token": token, "keys": keys}).encode("utf-8")
    req = urllib.request.Request(
        server + "/add_keys",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        print("সার্ভারে যোগাযোগ করা যায়নি:", exc)
        sys.exit(1)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("status") == "ok":
        print("\nসব ঠিক আছে। এখন এই key-গুলো বিতরণ করতে পারেন।")


if __name__ == "__main__":
    main()