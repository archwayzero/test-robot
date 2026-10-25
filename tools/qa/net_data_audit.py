#!/usr/bin/env python3
"""Network and data audit of the game, for the release QA (Prompt 4a). Static scan; a human still decides.

  python3 tools/qa/net_data_audit.py [--report docs/qa/reports/network-data-audit-scan.md]

Lists every place the game (including addons) can:
  - talk to the network (HTTP, sockets, WebSockets, multiplayer, URLs, opening links)
  - read device/user data (device IDs, clipboard, files outside the app's own storage, OS info)
  - run other programs or reach outside the engine (OS.execute, JavaScriptBridge, native plugins)
and the iOS permission texts in export_presets.cfg (camera, microphone, photos, location...).
The qa agent turns this into docs/qa/reports/network-data-audit.md (see .claude/agents/qa.md), which the
release package requires. This is a pattern scan: it finds the obvious, not every possible trick.
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
from scope_lib import repo_root  # noqa: E402

RULES = [
    ("network", r"\bHTTPRequest\b|\bHTTPClient\b", "HTTP request"),
    ("network", r"\bStreamPeerTCP\b|\bTCPServer\b|\bPacketPeerUDP\b|\bUDPServer\b|\bStreamPeerTLS\b", "raw socket"),
    ("network", r"\bWebSocketPeer\b|\bWebSocketMultiplayerPeer\b|\bWebRTC\w*", "WebSocket / WebRTC"),
    ("network", r"\bENetMultiplayerPeer\b|\bENetConnection\b|\bMultiplayerAPI\b|\bmultiplayer\.", "multiplayer networking"),
    ("network", r"https?://[^\s\"')]+", "URL in code"),
    ("network", r"\bOS\.shell_open\b", "opens a link/app outside the game"),
    ("data", r"\bOS\.get_unique_id\b", "device unique ID"),
    ("data", r"\bOS\.get_model_name\b|\bOS\.get_name\b|\bOS\.get_locale\b|\bOS\.get_environment\b", "device / OS info"),
    ("data", r"\bclipboard_get\w*\b", "reads the clipboard"),
    ("data", r"\bFileAccess\.open\s*\(\s*\"(?!user://|res://)", "file access outside the app's own storage"),
    ("data", r"\bDirAccess\.open\s*\(\s*\"(?!user://|res://)", "folder access outside the app's own storage"),
    ("data", r"\bOS\.get_system_dir\b|\bOS\.get_user_data_dir\b", "system / user folders"),
    ("data", r"\bInput\.get_accelerometer\b|\bInput\.get_gyroscope\b|\bInput\.get_magnetometer\b", "motion sensors"),
    ("data", r"\bCameraServer\b|\bAudioEffectCapture\b|\bAudioEffectRecord\b", "camera / microphone"),
    ("external", r"\bOS\.execute\w*\b|\bOS\.create_process\b|\bOS\.kill\b", "runs other programs"),
    ("external", r"\bJavaScriptBridge\b|\bEngine\.get_singleton\b", "native / platform bridge"),
]
SCAN_EXT = {".gd", ".tscn", ".tres", ".cs", ".gdshader", ".cfg", ".json"}
IOS_PERMISSION = re.compile(r'^(privacy/[^=]*usage_description[^=]*)="(.*)"', re.M)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report")
    a = ap.parse_args()
    godot = repo_root() / "godot"
    if not godot.is_dir():
        sys.exit("godot/ not found")
    findings = []
    for p in sorted(godot.rglob("*")):
        rel = p.relative_to(godot.parent).as_posix()
        if not p.is_file() or "/.godot/" in f"/{rel}" or "/tests/" in rel or p.suffix not in SCAN_EXT:
            continue
        if p.name == "export_presets.cfg":
            continue
        for n, line in enumerate(p.read_text(errors="ignore").splitlines(), 1):
            for cat, pat, what in RULES:
                if re.search(pat, line):
                    findings.append((cat, what, rel, n, line.strip()[:140], rel.startswith("godot/addons/")))
    perms = []
    ep = godot / "export_presets.cfg"
    if ep.exists():
        perms = [(k, v) for k, v in IOS_PERMISSION.findall(ep.read_text(errors="ignore")) if v.strip()]
    addons = sorted(d.name for d in (godot / "addons").glob("*") if d.is_dir()) if (godot / "addons").is_dir() else []

    lines = ["# Network and data audit: automated scan", "",
             "Static pattern scan of godot/ (tests excluded). Every finding needs a human-readable justification in",
             "docs/qa/reports/network-data-audit.md. Absence of findings is not proof of absence.", ""]
    for cat, title in (("network", "Network access"), ("data", "Device and user data"), ("external", "Outside the engine")):
        rows = [f for f in findings if f[0] == cat]
        lines += [f"## {title} ({len(rows)})", ""]
        if rows:
            lines += ["| what | where | third-party addon | code |", "|---|---|---|---|"]
            lines += [f"| {w} | {r}:{n} | {'yes' if ad else 'no'} | `{c.replace('|', '/')}` |" for _, w, r, n, c, ad in rows]
        else:
            lines.append("None found.")
        lines.append("")
    lines += ["## iOS permission texts in export_presets.cfg", ""]
    lines += [f"- `{k}`: {v}" for k, v in perms] or ["None set (the game asks for no camera, microphone, photos, location, etc.)."]
    lines += ["", "## Third-party addons (review what each sends and collects)", ""]
    lines += [f"- {x}" for x in addons] or ["None."]
    report = "\n".join(lines) + "\n"
    if a.report:
        Path(a.report).parent.mkdir(parents=True, exist_ok=True)
        Path(a.report).write_text(report)
    print(report)
    print(f"{len(findings)} findings, {len(perms)} iOS permission texts, {len(addons)} addons.")


if __name__ == "__main__":
    main()
