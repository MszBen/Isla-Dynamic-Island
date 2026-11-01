"""Relay run by Claude Code hooks. Stdlib only. Never blocks the agent if Isla is down."""
import json
import os
import sys
import urllib.request

PORT = int(os.environ.get("ISLA_PORT", "47821"))


def main() -> int:
    try:
        raw = sys.stdin.read()
        json.loads(raw)  # reject garbage early
        req = urllib.request.Request(
            f"http://127.0.0.1:{PORT}/event", data=raw.encode(), method="POST"
        )
        # Isla itself gives up on approvals after ~110s; allow a little longer here.
        with urllib.request.urlopen(req, timeout=125) as resp:
            body = resp.read().decode()
        if body:
            sys.stdout.write(body)
    except Exception:
        pass  # Isla not running / timeout -> exit silently, Claude Code carries on
    return 0


if __name__ == "__main__":
    sys.exit(main())
