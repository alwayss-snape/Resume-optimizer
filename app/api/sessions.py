"""Per-visitor state for the web API (P5.1).

Holds what Streamlit kept in st.session_state: the uploaded resume's temp
file, the checked parse, the analysed JD, the proposals and gap questions,
and the output folder. Kept in memory, keyed by an opaque random id sent as
a cookie, and dropped (temp files included) after `ttl_seconds` without a
request. The interface is small on purpose so it can move to Redis later.
"""
import os
import secrets
import shutil
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from app.services.profile_store import MemoryProfileStore

# Keys that point at temp files or folders owned by the session.
FILE_KEYS = ("resume_path", "output_dir")


@dataclass
class Session:
    id: str
    touched: float = field(default_factory=time.monotonic)
    data: Dict[str, Any] = field(default_factory=dict)
    # Held while a long step (drafting, tailoring) runs, so a second request
    # from the same visitor can't interleave with it.
    busy: threading.Lock = field(default_factory=threading.Lock)
    # Gap answers this visitor confirmed (P3.2), kept for their next JD in
    # this session only; the on-disk profile is shared, so never used here.
    profile: MemoryProfileStore = field(default_factory=MemoryProfileStore)
    # "Start over" arrived while a step was running: reset when it ends.
    reset_pending: bool = False

    def reset(self, keep: Optional[Dict[str, Any]] = None) -> None:
        """Delete the session's temp files and forget everything."""
        for key in FILE_KEYS:
            remove_path(self.data.get(key))
        self.data = dict(keep or {})


def remove_path(path: Optional[str]) -> None:
    if not path or not os.path.exists(path):
        return
    try:
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
        else:
            os.remove(path)
    except OSError:
        pass


class SessionStore:
    def __init__(self, ttl_seconds: int = 3600):
        self.ttl_seconds = ttl_seconds
        self._sessions: Dict[str, Session] = {}
        self._lock = threading.Lock()

    def get(self, session_id: Optional[str]) -> Optional[Session]:
        self.sweep()
        with self._lock:
            session = self._sessions.get(session_id or "")
            if session is not None:
                session.touched = time.monotonic()
            return session

    def create(self) -> Session:
        session = Session(id=secrets.token_urlsafe(24))
        with self._lock:
            self._sessions[session.id] = session
        return session

    def drop(self, session: Session) -> None:
        """Forget a session now, deleting its temp files."""
        with self._lock:
            self._sessions.pop(session.id, None)
        session.reset()

    def sweep(self, now: Optional[float] = None) -> int:
        """Drop sessions idle longer than the TTL; returns how many. A
        session whose step is still running is kept until it finishes."""
        now = time.monotonic() if now is None else now
        with self._lock:
            stale = [s for s in self._sessions.values()
                     if now - s.touched > self.ttl_seconds and not s.busy.locked()]
            for s in stale:
                del self._sessions[s.id]
        for s in stale:
            s.reset()
        return len(stale)

    def __len__(self) -> int:
        return len(self._sessions)
