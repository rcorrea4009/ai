"""
Live-trading lock. The Paper (Demo) side and all analysis are open to anyone the
app is shared with. Switching to LIVE (real-money) mode requires a password that
only the owner knows.

Security model:
- Only a salted SHA-256 HASH of the password is stored (in .env as LIVE_UNLOCK_HASH).
- The plaintext password is never stored and never seen by anyone but the owner,
  who sets it via scripts/set_password.py.
- If no hash is configured, LIVE mode is disabled entirely (fail-safe).
"""
import os
import hashlib
import streamlit as st

_SALT = "kronos-live-guard-v1"


def hash_password(pw: str) -> str:
    return hashlib.sha256((_SALT + pw).encode("utf-8")).hexdigest()


def demo_only() -> bool:
    """When DEMO_ONLY is set (e.g. on the public cloud deploy), live is impossible."""
    return os.environ.get("DEMO_ONLY", "").strip().lower() in ("1", "true", "yes")


def is_configured() -> bool:
    """True once the owner has set a live-trading password (and not in demo-only)."""
    if demo_only():
        return False
    return bool(os.environ.get("LIVE_UNLOCK_HASH"))


def check(pw: str) -> bool:
    stored = os.environ.get("LIVE_UNLOCK_HASH", "")
    return bool(stored) and hash_password(pw) == stored


def live_unlocked() -> bool:
    return bool(st.session_state.get("_live_unlocked"))


def try_unlock(pw: str) -> bool:
    if check(pw):
        st.session_state["_live_unlocked"] = True
        return True
    return False


def lock():
    st.session_state["_live_unlocked"] = False
