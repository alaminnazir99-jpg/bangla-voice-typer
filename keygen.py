"""Generate Bangla VoiceTyper license keys for selling.

Usage:
    python keygen.py            # print 1 key
    python keygen.py 10         # print 10 keys
"""

import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.license import generate_keys  # noqa: E402


def main():
    count = 1
    if len(sys.argv) > 1:
        try:
            count = max(1, int(sys.argv[1]))
        except ValueError:
            count = 1
    for key in generate_keys(count):
        print(key)


if __name__ == "__main__":
    main()