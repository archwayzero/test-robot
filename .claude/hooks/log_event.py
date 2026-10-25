#!/usr/bin/env python3
"""PostToolUse hook (Bash, async): append a JSON line for workflow-relevant commands.
Log file is gitignored. Swap for an HTTP hook if you want to feed a task tracker."""
import datetime
import json
import os
import re
import sys

try:
    data = json.load(sys.stdin)
    cmd = (data.get("tool_input") or {}).get("command", "")
    if re.search(r"\b(git\s+(commit|push|switch|checkout|merge)|dvc\s+(add|push|pull|checkout)|tools/task\.py|blender|godot)\b", cmd):
        root = os.environ.get("CLAUDE_PROJECT_DIR", ".")
        path = os.path.join(root, ".claude", "logs", "events.jsonl")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        rec = {"ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
               "agent": data.get("agent_type") or "orchestrator",
               "cwd": data.get("cwd"), "cmd": cmd[:500]}
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
except Exception:
    pass
sys.exit(0)
