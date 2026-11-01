import json

from isla import hooks_install
from isla.agents import Session, apply_event, describe_tool
from isla.lyrics import current_index, parse_lrc
from isla.shelf import Shelf


def test_parse_lrc_sorted_and_multistamp():
    lines = parse_lrc("[00:12.50]hello\n[00:05.00][00:30.00]chorus\nno stamp\n")
    assert [(l.time, l.text) for l in lines] == [(5.0, "chorus"), (12.5, "hello"), (30.0, "chorus")]


def test_current_index():
    lines = parse_lrc("[00:05.00]a\n[00:10.00]b")
    assert current_index(lines, 1) == -1
    assert current_index(lines, 5) == 0
    assert current_index(lines, 99) == 1


def test_describe_tool():
    assert describe_tool("Read", {"file_path": "C:/x/foo.py"}) == "Reading foo.py"
    assert describe_tool("Bash", {"command": "pytest -q"}) == "Running pytest -q"
    assert describe_tool("Weird", {}) == "Using Weird"


def test_apply_event_lifecycle():
    sessions: dict[str, Session] = {}
    apply_event(sessions, {"session_id": "a", "hook_event_name": "PreToolUse", "cwd": "C:/p/proj",
                           "tool_name": "Edit", "tool_input": {"file_path": "m.py"}})
    s = sessions["a"]
    assert (s.status, s.activity, s.project) == ("working", "Editing m.py", "proj")
    apply_event(sessions, {"session_id": "a", "hook_event_name": "Stop"})
    assert s.status == "done"
    apply_event(sessions, {"session_id": "a", "hook_event_name": "SessionEnd"})
    assert "a" not in sessions


def test_hook_merge_idempotent_and_preserves_others():
    base = {"model": "x", "hooks": {"Stop": [{"matcher": "", "hooks": [{"type": "command", "command": "mine"}]}]}}
    once = hooks_install.merge(base, "python isla_hook.py")
    twice = hooks_install.merge(once, "python isla_hook.py")
    assert once == twice
    assert once["model"] == "x"
    assert len(once["hooks"]["Stop"]) == 2  # user's hook kept + ours
    assert hooks_install.remove(once) == base


def test_shelf_roundtrip(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("hi")
    store = tmp_path / "shelf.json"
    s = Shelf(store)
    assert s.add([str(f), str(f), str(tmp_path / "nope")]) == 1
    assert [i.name for i in Shelf(store).items] == ["a.txt"]
    s.remove(str(f.resolve()) if False else s.items[0].path)
    assert Shelf(store).items == []
    assert json.loads(store.read_text()) == []


def test_permission_request_roundtrip():
    import threading
    from isla.agents import AgentHub

    hub = AgentHub(0, approval_timeout=5)
    hub.approval_requested.connect(lambda ap: threading.Timer(0.05, hub.resolve, (ap.id, "allow")).start())
    out = json.loads(hub.handle({"session_id": "s", "hook_event_name": "PermissionRequest",
                                 "tool_name": "Bash", "tool_input": {"command": "ls"}}))
    assert out["hookSpecificOutput"]["decision"]["behavior"] == "allow"


def test_permission_timeout_falls_back():
    from isla.agents import AgentHub

    hub = AgentHub(0, approval_timeout=0.1)
    assert hub.handle({"session_id": "s", "hook_event_name": "PermissionRequest", "tool_name": "Bash"}) == ""


def test_hooks_is_installed(tmp_path):
    f = tmp_path / "settings.json"
    assert hooks_install.is_installed(f) is False
    f.write_text("not json")
    assert hooks_install.is_installed(f) is False
    f.write_text(json.dumps(hooks_install.merge({}, "python isla_hook.py")))
    assert hooks_install.is_installed(f) is True


def test_config_ignores_unknown_and_roundtrips(tmp_path):
    from isla.config import Config
    f = tmp_path / "c.json"
    f.write_text(json.dumps({"ghost_opacity": 0.4, "bogus": 1}))
    c = Config.load(f)
    assert c.ghost_opacity == 0.4
    c.save(f)
    assert "bogus" not in json.loads(f.read_text())


def test_power_interpret():
    from isla.power import interpret
    assert interpret(1, 8, 80) == (True, 80)
    assert interpret(0, 1, 42) == (False, 42)
    assert interpret(1, 128, 255) is None  # desktop, no battery


def test_is_headphones():
    from isla.devices import is_headphones
    assert is_headphones("Headphones (WH-1000XM5 Hands-Free)")
    assert not is_headphones("Speakers (Realtek Audio)")


def test_transcript_usage_and_run_tokens(tmp_path):
    from isla.agents import Session, transcript_usage
    assert transcript_usage({"type": "user"}) is None
    f = tmp_path / "t.jsonl"
    old = {"type": "assistant", "message": {"id": "m0", "usage": {"input_tokens": 999, "output_tokens": 1}}}
    f.write_text(json.dumps(old) + "\n")
    s = Session("a", transcript=str(f))
    s.start_run()  # baseline: earlier history isn't counted
    a1 = {"type": "assistant", "message": {"id": "m1", "usage": {"input_tokens": 10, "output_tokens": 5, "cache_creation_input_tokens": 100, "cache_read_input_tokens": 9999}}}
    a1b = {"type": "assistant", "message": {"id": "m1", "usage": {"input_tokens": 10, "output_tokens": 20, "cache_creation_input_tokens": 100}}}
    with open(f, "a") as fh:
        fh.write(json.dumps(a1) + "\n" + json.dumps(a1b) + "\n" + '{"type": "assist')  # partial last line
    s.read_tokens()
    assert s.tokens == 130  # same message id counted once (max), cache reads excluded
    with open(f, "a") as fh:
        fh.write('ant", "message": {"id": "m2", "usage": {"output_tokens": 7}}}\n')
    s.read_tokens()
    assert s.tokens == 137


def test_active_session_and_no_restart_after_stop():
    from isla.agents import AgentHub
    hub = AgentHub(0)
    hub.handle({"session_id": "a", "hook_event_name": "UserPromptSubmit", "cwd": "C:/p/x"})
    assert hub.active_session().id == "a"
    hub.handle({"session_id": "a", "hook_event_name": "Stop"})
    assert hub.active_session() is None
    hub.handle({"session_id": "a", "hook_event_name": "PostToolUse", "tool_name": "Read"})
    assert hub.active_session() is None


def test_allow_always_uses_claudes_own_suggestion():
    import threading
    from isla.agents import AgentHub

    hub = AgentHub(0, approval_timeout=5)
    sugg = [{"type": "addRules", "rules": [{"toolName": "Bash", "ruleContent": "pytest"}],
             "behavior": "allow", "destination": "localSettings"}]
    hub.approval_requested.connect(lambda ap: threading.Timer(0.05, hub.resolve, (ap.id, "always")).start())
    out = json.loads(hub.handle({"session_id": "s", "hook_event_name": "PermissionRequest", "tool_name": "Bash",
                                 "tool_input": {"command": "pytest"}, "permission_suggestions": sugg}))
    d = out["hookSpecificOutput"]["decision"]
    assert d["behavior"] == "allow" and d["updatedPermissions"] == sugg


def test_allow_always_without_suggestion_is_safe():
    from isla.agents import Approval
    assert Approval("s", "Bash", "x").can_always is False  # never a blanket Bash rule
    ap = Approval("s", "Edit", "x")
    assert ap.can_always and ap.always_updates()[0]["rules"] == [{"toolName": "Edit"}]


def test_deny_decision():
    import threading
    from isla.agents import AgentHub

    hub = AgentHub(0, approval_timeout=5)
    hub.approval_requested.connect(lambda ap: threading.Timer(0.05, hub.resolve, (ap.id, "deny")).start())
    out = json.loads(hub.handle({"session_id": "s", "hook_event_name": "PermissionRequest", "tool_name": "Bash"}))
    assert out["hookSpecificOutput"]["decision"]["behavior"] == "deny"


def test_request_dismissed_when_answered_elsewhere():
    import threading
    import time
    from isla.agents import AgentHub

    hub = AgentHub(0, approval_timeout=5)
    finished = []
    hub.approval_finished.connect(finished.append)
    perm = {"session_id": "s", "hook_event_name": "PermissionRequest", "tool_name": "Bash", "tool_input": {"command": "ls"}}
    # tool ran (answered in the terminal / desktop app) -> PostToolUse for the same call
    threading.Timer(0.1, hub.handle, ({"session_id": "s", "hook_event_name": "PostToolUse",
                                       "tool_name": "Bash", "tool_input": {"command": "ls"}},)).start()
    t0 = time.monotonic()
    assert hub.handle(perm) == ""
    assert time.monotonic() - t0 < 2 and len(finished) == 1


def test_request_dismissed_when_relay_hangs_up():
    import socket
    import threading
    import time
    from isla.agents import AgentHub

    hub = AgentHub(0, approval_timeout=5)
    server_side, client_side = socket.socketpair()
    threading.Timer(0.1, client_side.close).start()  # Claude Code killed the hook
    t0 = time.monotonic()
    assert hub.handle({"session_id": "s", "hook_event_name": "PermissionRequest", "tool_name": "Read"}, server_side) == ""
    assert time.monotonic() - t0 < 2


def test_confetti_spawn_and_physics():
    import random
    from isla.confetti import LIFE, PALETTES, spawn

    ps = spawn(50, (100, 30), PALETTES["claude"], random.Random(1))
    assert len(ps) == 50 and all(p.alive for p in ps)
    vy0 = [p.vy for p in ps]
    for p in ps:
        p.advance(0.1)
    assert sum(p.vy > v for p, v in zip(ps, vy0)) > 40          # gravity pulls pieces down
    for p in ps:
        p.advance(LIFE)
    assert not any(p.alive for p in ps) and all(p.opacity == 0 for p in ps)
