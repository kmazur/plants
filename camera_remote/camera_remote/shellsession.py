"""Persistent PTY shell sessions for the browser terminal (xterm.js).

The stdlib HTTP server has no WebSocket support, so the terminal uses plain
HTTP long-polling: the browser POSTs keystrokes and GETs new output by byte
offset. Each session is a real PTY running an interactive shell, so it handles
interactive prompts (sudo, debconf, ...), colours and long-running processes.
"""
from __future__ import annotations

import errno
import fcntl
import logging
import os
import pty
import secrets
import select
import shutil
import signal
import struct
import termios
import threading
import time
from typing import Dict, Optional, Tuple

log = logging.getLogger(__name__)

MAX_SESSIONS = 4
BUFFER_CAP = 256 * 1024
IDLE_TIMEOUT = 900  # seconds


def _pick_shell() -> str:
    return shutil.which("bash") or shutil.which("sh") or "/bin/sh"


class ShellSession:
    def __init__(self, sid: str, rows: int = 24, cols: int = 80, cap: int = BUFFER_CAP):
        self.sid = sid
        self.last_access = time.monotonic()
        self.alive = True
        self._cap = cap
        self._buf = bytearray()
        self._base = 0  # bytes already trimmed from the front
        self._cond = threading.Condition()

        shell = _pick_shell()
        self.pid, self._fd = pty.fork()
        if self.pid == 0:  # child
            try:
                os.environ["TERM"] = "xterm-256color"
                os.execvp(shell, [shell, "-i"])
            except Exception:
                os._exit(1)
        self._set_winsize(rows, cols)
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    def _set_winsize(self, rows: int, cols: int) -> None:
        try:
            rows = max(1, min(300, int(rows)))
            cols = max(1, min(500, int(cols)))
            fcntl.ioctl(self._fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
        except Exception:
            pass

    def _read_loop(self) -> None:
        while True:
            try:
                r, _, _ = select.select([self._fd], [], [], 0.5)
            except (OSError, ValueError):
                break
            if self._fd not in r:
                continue
            try:
                data = os.read(self._fd, 65536)
            except OSError as exc:
                if exc.errno == errno.EIO:  # slave closed (shell exited)
                    break
                continue
            if not data:
                break
            with self._cond:
                self._buf += data
                if len(self._buf) > self._cap:
                    drop = len(self._buf) - self._cap
                    del self._buf[:drop]
                    self._base += drop
                self._cond.notify_all()
        with self._cond:
            self.alive = False
            self._cond.notify_all()

    def write(self, data: bytes) -> None:
        self.last_access = time.monotonic()
        try:
            os.write(self._fd, data)
        except OSError:
            pass

    def resize(self, rows: int, cols: int) -> None:
        self.last_access = time.monotonic()
        self._set_winsize(rows, cols)

    def read_since(self, pos: int, timeout: float = 2.0) -> Tuple[bytes, int, bool]:
        self.last_access = time.monotonic()
        with self._cond:
            end = self._base + len(self._buf)
            if pos >= end and self.alive:
                self._cond.wait(timeout)
                end = self._base + len(self._buf)
            start = max(0, pos - self._base)
            data = bytes(self._buf[start:])
            new_pos = self._base + len(self._buf)
            return data, new_pos, self.alive

    def close(self) -> None:
        self.alive = False
        try:
            os.kill(self.pid, signal.SIGHUP)
        except Exception:
            pass
        try:
            os.close(self._fd)
        except Exception:
            pass
        try:
            os.waitpid(self.pid, os.WNOHANG)
        except Exception:
            pass


class ShellManager:
    def __init__(self, idle_timeout: int = IDLE_TIMEOUT, max_sessions: int = MAX_SESSIONS):
        self._sessions: Dict[str, ShellSession] = {}
        self._lock = threading.Lock()
        self._idle = idle_timeout
        self._max = max_sessions
        self._reaper = threading.Thread(target=self._reap_loop, daemon=True)
        self._reaper.start()

    def open(self, rows: int = 24, cols: int = 80) -> ShellSession:
        with self._lock:
            # drop any already-dead sessions before enforcing the cap
            for sid in [s for s, sess in self._sessions.items() if not sess.alive]:
                self._sessions.pop(sid, None)
            if len(self._sessions) >= self._max:
                raise RuntimeError("too many shell sessions")
            sid = secrets.token_hex(8)
            session = ShellSession(sid, rows=rows, cols=cols)
            self._sessions[sid] = session
            return session

    def get(self, sid: str) -> Optional[ShellSession]:
        with self._lock:
            return self._sessions.get(sid)

    def close(self, sid: str) -> None:
        with self._lock:
            session = self._sessions.pop(sid, None)
        if session is not None:
            session.close()

    def _reap_loop(self) -> None:
        while True:
            time.sleep(10)
            now = time.monotonic()
            dead = []
            with self._lock:
                for sid, session in list(self._sessions.items()):
                    if not session.alive or now - session.last_access > self._idle:
                        dead.append(self._sessions.pop(sid))
            for session in dead:
                session.close()
