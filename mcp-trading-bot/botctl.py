#!/usr/bin/env python3
"""Isaac's control CLI (Phase 1.5): the human-side toggle and kill switch.

Usage:
  python3 botctl.py status
  python3 botctl.py active  [-m "why"]
  python3 botctl.py pause   [-m "why"]
  python3 botctl.py stop    [-m "why"]     # kill switch: flattens everything
  python3 botctl.py account
  python3 botctl.py log [-n 20]

Reads BOT_SERVER_URL (default http://127.0.0.1:8000).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

BASE_URL = os.environ.get("BOT_SERVER_URL", "http://127.0.0.1:8000")


def call(method: str, path: str, payload: dict | None = None):
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        method=method,
        headers={"Content-Type": "application/json"},
        data=json.dumps(payload).encode() if payload is not None else None,
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"ERROR {e.code}: {e.read().decode()}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"ERROR: bot server unreachable at {BASE_URL} ({e.reason})", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Trading bot control CLI")
    parser.add_argument("command", choices=["status", "active", "pause", "stop", "account", "log"])
    parser.add_argument("-m", "--message", default="", help="reason for the state change")
    parser.add_argument("-n", "--limit", type=int, default=20, help="log entries to show")
    args = parser.parse_args()

    if args.command == "status":
        out = call("GET", "/status")
    elif args.command == "account":
        out = call("GET", "/account")
    elif args.command == "log":
        out = call("GET", f"/log?limit={args.limit}")
    else:
        state = {"active": "ACTIVE", "pause": "PAUSED", "stop": "STOPPED"}[args.command]
        out = call("POST", "/control", {"state": state, "reason": args.message or f"botctl {args.command}"})

    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
