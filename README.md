# Godot + Blender game kit for Claude Code

A starter architecture for an orchestrator that delegates to scope-limited subagents, with git + DVC
ordering enforced by hooks instead of prompts.

**Start with [SETUP.md](SETUP.md)**: everything you must do before handing over to the agents (WSL2, the
Claude Code sandbox, GitHub, AWS, ComfyUI). The rest of this file is reference.

## How it runs
- Claude Code runs inside **WSL2** (Ubuntu on Windows) with **Claude Code's built-in sandbox** switched on in
  `.claude/settings.json`. No Docker, no containers.
- The sandbox is enforced by the operating system for every shell command the agents run: writes only inside the
  project folder (minus the locked rule files), Windows drives unreadable, and network access only to GitHub, your
  S3 bucket and ComfyUI on `localhost:8188`. `failIfUnavailable` makes Claude refuse to start rather than run
  unprotected. Claude's own file tools are kept in the project by its permission rules and the kit's hooks.
- **GPU:** ComfyUI on Windows uses your GPU. Commands inside the sandbox cannot see the GPU, so Blender snapshots
  and Godot screenshots render on the CPU (seconds per image at the sizes used here).
- **MCP servers on localhost** work as usual: Claude Code connects to them itself, outside the sandbox.

## ComfyUI
ComfyUI runs on Windows as it does now. WSL2's *mirrored* networking (SETUP.md) makes it reachable at
`http://localhost:8188`. Inside the sandbox each command has a private localhost, so `tools/comfy/comfy_client.py`
goes through the sandbox's network proxy, which allows exactly `localhost:8188`.
- Export your workflow in API format into `tools/comfy/workflows/` with its `.map.json` (README there).
  The agent can only change the inputs listed in the map, and only read/write files inside the repo.
- Custom nodes in ComfyUI run on Windows, outside the sandbox. Agents cannot install them.

## Asset storage on AWS S3 (DVC remote)
DVC talks to S3 itself with a limited IAM user (read and add files in `<bucket>/dvc/` only, no delete) whose
keys live in `~/.aws` in WSL. `tools/setup.sh` adds your bucket's address to the sandbox's network allowlist.
Agents cannot change the remote or DVC config (blocked by the bash guard and the sandbox).

## Adding a model you made elsewhere (e.g. Tripo)
Copy it to `blender/models/<id>/source/<id>_tripo.glb` and ask Claude to create a modeler task that tracks it
with DVC and commits it unchanged (exact wording in SETUP.md, part H). Then list it in `docs/specs/ASSETS.md` with
`source: provided: <path>`. Prompt 2 plans: modeler conforms it -> reference-director -> rigger-animator -> qa.

## Playing previews on your PC
Copy the Godot folder out of the project and open the copy with the same Godot version on Windows (SETUP.md,
part I). Don't open the agents' working folder directly: the editor writes files into it. Game scripts run with
your Windows permissions, outside the sandbox, so only play versions you've reviewed.

## What is in the box
| Path | Purpose |
|---|---|
| `CLAUDE.md` | short root rules, loaded by every agent |
| `docs/architecture/` | module model, workflow, version-control order |
| `docs/contracts/blender-godot-assets.md` | naming, units, export conventions |
| `docs/module-map.json` | per-agent write scopes, binary extensions (locked) |
| `docs/modules.json` | module list and dependencies (orchestrator) |
| `.claude/settings.json` | sandbox config, permission rules, hooks, and `agent: orchestrator` for the main session |
| `.claude/hooks/` | scope guard, bash guard, completion gate, event log |
| `.claude/agents/` | orchestrator, modeler, reference-director, rigger-animator, qa, reviewer and a generic `module-dev` scoped by its task branch |
| `.claude/skills/ref-to-video/` | reference video procedure, preloaded by reference-director |
| `docs/specs/PLATFORM.md`, `docs/qa/` | platform constraints, test plan, budgets, QA reports |
| `tools/qa/check_budgets.py` | static budget check of exported .glb files, with score |
| `tools/qa/net_data_audit.py` | release scan: network access, device/user data, iOS permissions, addons |
| `tools/comfy/`, `tools/blender/render_snapshot.py` | ComfyUI client and snapshot renderer |
| `tools/envcheck.py`, `tools/sandbox_selftest.py` | environment report; proof the sandbox protections are active |
| `tools/qa/record.py` | MP4 gameplay videos of scripted playthroughs, for human review without running code |
| `tools/qa/capture.py`, `tools/xdisplay.py` | Godot scene screenshots agents can read (works inside the sandbox) |
| `SETUP.md` | human setup checklist (locked against agents) |
| `MAINTAINING.md`, `tools/maintain.sh` | how kit fixes are made: a separate, unsandboxed maintenance session in its own clone, via PRs |
| `tools/tests/run_all.sh` | the kit's test suites (Linux); also run on PRs by `.github/workflows/kit-tests.yml` |
| `tools/release/make_mac_package.py` | gated release package (Godot project + DVC assets) for the Mac |
| `tools/githooks/` | pre-commit, pre-push (`dvc push` before git push), post-checkout (`dvc checkout`) |
| `tools/*.py`, `tools/setup.sh` | scaffolding, task ledger, commit checks, one-time setup + self-test |

## Design decisions worth knowing
- Git hooks live in `tools/githooks` and are activated with `core.hooksPath`, not `dvc install`. They are versioned,
  survive fresh clones, and `dvc install` refuses to run when a hook already exists. They call the same DVC commands.
- Per-agent scoping uses the `agent_type` field Claude Code passes to hooks, so it works inside subagents.
  Agents not listed in the module map cannot write at all.
- Blender work is done through headless Python scripts. Scripts are the source of truth; `.blend`/`.glb` are DVC artifacts.

## Honest limits
- The sandbox covers shell commands. Claude's own file tools are limited by permission rules and the scope hook;
  MCP servers do whatever they are built to do. Hooks themselves run outside the sandbox (they are the kit's code).
- Inside the sandbox, files are readable unless denied: the kit denies Windows drives (`/mnt`) and `~/.ssh`. The
  limited AWS keys and GitHub token are readable by design (DVC and git need them) but can only reach GitHub and your bucket.
- Uploads are limited to GitHub and your bucket, not prevented there: the scoped token and IAM user limit the damage.
- The decoupling check scans `res://modules/...` references only. It cannot see runtime coupling.
- Scripted modeling gives simple, stylized geometry; organic sculpting, texture painting, and polished
  animation still need human art or other tools. Expect to review every asset.
- One task at a time per checkout. Parallel agents need git worktrees (see WORKFLOW.md).
- Guard hooks need Claude Code 2.1.295+; on older versions a crashing hook would not block. Check `claude --version`.
- Static budget score covers triangles, draw-call estimate, joints and texture sizes from .glb files only. Frame time
  and GPU cost are measured on device (Mac + Xcode) at the end.
- Generated reference videos drift in proportion and timing: they guide animation, they do not approve it.
- Tested outside your setup: the hooks and scripts were tested on Linux with simulated hook input, a stand-in `dvc`,
  and Linux namespaces in place of the real sandbox. `tools/sandbox_selftest.py`, run by Claude inside the sandbox,
  is the real check on your PC.
