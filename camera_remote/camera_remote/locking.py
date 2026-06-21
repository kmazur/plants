from __future__ import annotations

import fcntl
from pathlib import Path


class CameraBusy(RuntimeError):
    pass


class CameraLock:
    def __init__(self, path: Path, blocking: bool = True):
        self.path = path
        self.blocking = blocking
        self._fh = None

    def __enter__(self) -> "CameraLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self.path.open("w")
        flags = fcntl.LOCK_EX
        if not self.blocking:
            flags |= fcntl.LOCK_NB
        try:
            fcntl.flock(self._fh.fileno(), flags)
        except BlockingIOError as exc:
            self._fh.close()
            self._fh = None
            raise CameraBusy("camera is already in use") from exc
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._fh is not None:
            fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
            self._fh.close()
            self._fh = None

