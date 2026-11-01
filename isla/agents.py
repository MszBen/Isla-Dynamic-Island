"""AI agent management: session model + localhost server fed by hooks/isla_hook.py."""
from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import PurePath

from PySide6.QtCore import QObject, Signal


@dataclass
class Session:
    id: str
    cwd: str = ""
    status: str = "idle"  # idle | working | waiting | done
    activity: str = ""
    updated: float = field(default_factory=time.time)

    @property
    def project(self) -> str:
        return PurePath(self.cwd).name or "session"


@dataclass
class Approval:
    session_id: str
    tool: str
    summary: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    decision: str | None = None
    _done: threading.Event = field(default_factory=threading.Event, repr=False)


def describe_tool(tool: str, args: dict) -> str:
    """One-line human summary of a tool call."""
    args = args or {}

    def base(key: str) -> str:
        return PurePath(str(args.get(key, ""))).name or "file"

    if tool == "Read":
        return f"Reading {base('file_path')}"
    if tool in ("Edit", "MultiEdit"):
        return f"Editing {base('file_path')}"
    if tool == "Write":
        return f"Writing {base('file_path')}"
    if tool == "Bash":
        cmd = " ".join(str(args.get("command", "")).split())
        return "Running " + (cmd[:60] + "…" if len(cmd) > 60 else cmd)
    if tool in ("Grep", "Glob"):
        return f"Searching {args.get('pattern', '')}"[:70]
    if tool in ("WebFetch", "WebSearch"):
        return f"Browsing {args.get('url') or args.get('query', '')}"[:70]
    return f"Using {tool}" if tool else "Working"


def apply_event(sessions: dict[str, Session], payload: dict) -> Session | None:
    """Pure reducer: fold one hook payload into the session table. Returns the touched session."""
    sid = str(payload.get("session_id") or "unknown")
    event = payload.get("hook_event_name", "")
    if event == "SessionEnd":
        sessions.pop(sid, None)
        return None
    s = sessions.setdefault(sid, Session(sid))
    s.cwd = payload.get("cwd") or s.cwd
    s.updated = time.time()
    if event == "UserPromptSubmit":
        s.status, s.activity = "working", "Thinking…"
    elif event in ("PreToolUse", "PostToolUse"):
        s.status = "working"
        s.activity = describe_tool(payload.get("tool_name", ""), payload.get("tool_input") or {})
    elif event in ("Notification", "PermissionRequest"):
        s.status = "waiting"
        s.activity = payload.get("message") or "Needs your attention"
    elif event == "Stop":
        s.status, s.activity = "done", "Finished"
    elif event == "SessionStart":
        s.status, s.activity = "idle", "Started"
    return s


class AgentHub(QObject):
    """Owns the sessions and the hook server. Signals fire from server threads (queued to the UI)."""

    sessions_changed = Signal()
    approval_requested = Signal(object)
    approval_finished = Signal(str)  # approval id
    attention = Signal(str, str)  # kind: "done" | "waiting", text

    def __init__(self, port: int, approval_timeout: float = 110.0):
        super().__init__()
        self.port = port
        self.approval_timeout = approval_timeout
        self.sessions: dict[str, Session] = {}
        self._lock = threading.Lock()
        self._pending: dict[str, Approval] = {}
        self._server: ThreadingHTTPServer | None = None

    # -- lifecycle -------------------------------------------------------
    def start(self) -> bool:
        hub = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                try:
                    n = int(self.headers.get("Content-Length", 0))
                    payload = json.loads(self.rfile.read(n) or b"{}")
                    body = hub.handle(payload)
                except Exception:
                    body = ""
                data = body.encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *a) -> None:
                pass

        try:
            self._server = ThreadingHTTPServer(("127.0.0.1", self.port), Handler)
        except OSError:
            return False
        self._server.daemon_threads = True
        threading.Thread(target=self._server.serve_forever, daemon=True, name="isla-hooks").start()
        return True

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()

    # -- event handling (server threads) ---------------------------------
    def handle(self, payload: dict) -> str:
        """Process one hook payload; returns the hook's stdout JSON ('' = no opinion)."""
        event = payload.get("hook_event_name", "")
        with self._lock:
            s = apply_event(self.sessions, payload)
        self.sessions_changed.emit()
        if s and event == "Stop":
            self.attention.emit("done", f"{s.project} finished")
        elif s and event == "Notification":
            self.attention.emit("waiting", f"{s.project}: {s.activity}")
        if event == "PermissionRequest":
            return self._ask(payload)
        return ""

    def _ask(self, payload: dict) -> str:
        tool = payload.get("tool_name", "")
        ap = Approval(
            session_id=str(payload.get("session_id")),
            tool=tool,
            summary=describe_tool(tool, payload.get("tool_input") or {}),
        )
        self._pending[ap.id] = ap
        self.approval_requested.emit(ap)
        answered = ap._done.wait(self.approval_timeout)
        self._pending.pop(ap.id, None)
        self.approval_finished.emit(ap.id)
        if not answered or ap.decision not in ("allow", "deny"):
            return ""  # fall back to Claude Code's own prompt
        decision: dict = {"behavior": ap.decision}
        if ap.decision == "deny":
            decision["message"] = "Denied from Isla"
        return json.dumps(
            {"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": decision}}
        )

    # -- UI thread -------------------------------------------------------
    def resolve(self, approval_id: str, decision: str) -> None:
        ap = self._pending.get(approval_id)
        if ap:
            ap.decision = decision
            ap._done.set()

    def snapshot(self) -> list[Session]:
        with self._lock:
            return sorted(self.sessions.values(), key=lambda s: -s.updated)
