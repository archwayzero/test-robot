#!/usr/bin/env python3
"""PreToolUse hook (Bash): block commands that bypass the version-control order.

Heuristic by nature (shell is expressive). Hard guarantees come from the git hooks,
the CI scope check, branch protection, and read-only file permissions in the sandbox.
"""
import json
import re
import shlex
import sys

PROTECTED_PATHS = [".claude/settings", ".claude/hooks", "tools/githooks", "tools/scope_lib",
                   "tools/precommit_checks", "tools/comfy/comfy_client", "tools/sandbox_selftest",
                   "tools/setup.sh", "tools/envcheck", "tools/xdisplay", "tools/kit_update", "docs/module-map",
                   ".git/hooks", ".git/config", ".dvc/config"]
# Commands that change the files named in their arguments.
WRITING_COMMANDS = {"tee", "mv", "rm", "cp", "chmod", "chown", "truncate", "ln", "dd", "install", "touch", "rsync",
                    "unlink", "shred"}
# Redirections that write to a file: >, >>, >|, 1>, 2>>, &> ... but not fd duplication like 2>&1.
REDIRECT_TARGET = re.compile(r"(?:^|[^<>&\d])(?:\d|&)?>>?\|?(?!&)\s*([^\s;&|<>]+)")
MAIN = {"main", "master"}


def block(msg):
    print("Blocked: " + msg, file=sys.stderr)
    sys.exit(2)


def tokens_of(segment):
    try:
        toks = shlex.split(segment)
    except ValueError:
        toks = segment.split()
    while toks and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", toks[0]):
        toks = toks[1:]
    while toks and toks[0] in ("env", "command", "time", "nohup"):
        toks = toks[1:]
        while toks and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", toks[0]):
            toks = toks[1:]
    return toks


def git_sub(toks):
    i, hooks_path = 1, False
    while i < len(toks):
        t = toks[i]
        if t == "-c" and i + 1 < len(toks):
            if "hookspath" in toks[i + 1].lower():
                hooks_path = True
            i += 2
        elif t == "-C" and i + 1 < len(toks):
            i += 2
        elif t.startswith("-"):
            i += 1
        else:
            return t, toks[i + 1:], hooks_path
    return None, [], hooks_path


def check_segment(seg):
    toks = tokens_of(seg)
    if not toks:
        return
    if toks[0] in ("sudo", "su", "doas", "pkexec"):
        block("administrator commands are not allowed. Ask the human to install or change system software.")
    if toks[0] in ("bash", "sh", "zsh") and "-c" in toks:
        idx = toks.index("-c")
        if idx + 1 < len(toks):
            check_command(toks[idx + 1])
        return
    if toks[0] == "git":
        sub, rest, hooks_path = git_sub(toks)
        if hooks_path:
            block("overriding core.hooksPath is not allowed.")
        flags = [t for t in rest if t.startswith("-")]
        if sub == "commit":
            if "--no-verify" in flags or any(re.fullmatch(r"-[A-Za-z]*n[A-Za-z]*", f) for f in flags):
                block("git commit --no-verify/-n skips the hooks. Fix what the hook reports instead.")
        elif sub == "push":
            if "--no-verify" in flags:
                block("git push --no-verify skips the DVC push hook.")
            if "-u" in flags or "--set-upstream" in flags:
                block("push without -u (the sandbox protects .git/config): git push origin <branch>")
            if any(f in ("--force", "-f", "--mirror", "--delete") or f.startswith("--force-with-lease") for f in flags):
                block("force/delete pushes are not allowed.")
            for t in rest:
                if not t.startswith("-") and (t in MAIN or t.split(":")[-1].split("/")[-1] in MAIN):
                    block("pushing to main/master is not allowed. Push the task branch; the human merges the PR.")
        elif sub == "config" and any("hookspath" in t.lower() for t in rest):
            block("changing core.hooksPath is not allowed.")
        elif sub == "remote" and rest and rest[0] in ("add", "set-url", "remove", "rm", "rename"):
            block("changing git remotes is not allowed. Ask the human.")
    elif toks[0] == "dvc" and len(toks) > 1:
        if toks[1] == "remote" and len(toks) > 2 and toks[2] in ("add", "modify", "remove", "default", "rename"):
            block("changing DVC remotes is not allowed (data could be redirected). Ask the human.")
        if toks[1] == "config" and len(toks) > 2 and any(re.search(r"remote|url|core", t) for t in toks[2:]):
            block("changing DVC config is not allowed. Ask the human.")


def is_protected(text):
    return any(p in text for p in PROTECTED_PATHS)


def writes_protected(cmd):
    """True only if the command writes to a protected path (not merely mentions or reads it)."""
    if not is_protected(cmd):
        return False
    if any(is_protected(t) for t in REDIRECT_TARGET.findall(cmd)):
        return True
    for seg in re.split(r"&&|\|\||;|\n|\|", cmd):
        toks = tokens_of(seg)
        if not toks:
            continue
        name = toks[0].rsplit("/", 1)[-1]
        args = toks[1:]
        if name in WRITING_COMMANDS and any(is_protected(t) for t in args):
            return True
        if name in ("sed", "perl") and any(t.startswith("-i") or t == "-pi" for t in args) and any(is_protected(t) for t in args):
            return True
        if re.fullmatch(r"python3?|node|ruby|perl|bash|sh|zsh", name) and "-c" in args or name in ("python3", "python") and "-e" in args:
            return True  # inline code that mentions a protected path: treat as a write attempt
        if name == "git" and len(args) >= 1 and args[0] in ("checkout", "restore") and any(is_protected(t) for t in args[1:]):
            return True
    return False


def check_command(cmd):
    if re.search(r"\bALLOW_[A-Z_]+", cmd):
        block("ALLOW_* override variables are for the human only.")
    if writes_protected(cmd):
        block("this command appears to modify locked enforcement files. Use the Read tool to inspect them; "
              "only the human may change them.")
    for seg in re.split(r"&&|\|\||;|\n|\|", cmd):
        check_segment(seg)


data = json.load(sys.stdin)
check_command((data.get("tool_input") or {}).get("command", ""))
sys.exit(0)
