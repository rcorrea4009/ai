"""
Set / change the LIVE-trading password. Run this yourself:

    venv\\Scripts\\python.exe scripts\\set_password.py

It asks for a password (hidden input), stores only its salted hash in .env as
LIVE_UNLOCK_HASH, and never records the plaintext. Only you will know it.
"""
import os
import sys
import getpass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.auth import hash_password

ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")


def main():
    print("Set the LIVE trading password (this unlocks real-money mode).")
    pw = getpass.getpass("New password: ")
    if len(pw) < 6:
        print("Too short — use at least 6 characters. Aborted.")
        return
    if pw != getpass.getpass("Confirm password: "):
        print("Passwords didn't match. Aborted.")
        return

    h = hash_password(pw)

    # read existing .env, replace or append LIVE_UNLOCK_HASH
    lines, found = [], False
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
    for i, ln in enumerate(lines):
        if ln.startswith("LIVE_UNLOCK_HASH="):
            lines[i] = f"LIVE_UNLOCK_HASH={h}"
            found = True
            break
    if not found:
        lines.append(f"LIVE_UNLOCK_HASH={h}")
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print("\n✅ Password set. Live mode now requires it. Restart the app to load it.")
    print("   (Only the hash is stored; your password is not saved anywhere.)")


if __name__ == "__main__":
    main()
