# Setup guide (for you, the human)

This guide gets everything ready so the AI agents can start building your game. Go from top to bottom. Don't
skip ahead: later steps depend on earlier ones.

**How it works, in one paragraph:** the agents run inside **Ubuntu on Windows (WSL2)**, with **Claude Code's
built-in sandbox** switched on. The sandbox is enforced by the operating system: the agents' commands can only
change files in your project folder, can't see your Windows files (including your browser logins), and can only
connect to GitHub, your storage bucket, and ComfyUI. If the sandbox can't start, Claude refuses to run. No Docker,
no virtual machines to manage.

- **Time:** plan for an afternoon. Parts A to D are one-time setup.
- **Checkboxes:** tick each `[ ]` as you finish it.
- **Stuck?** Take a screenshot and paste it into a Claude chat (in the normal Claude app, not the project) with the
  step number. Websites rename buttons over time; if one isn't exactly where described, look for a similar name.
- **Secrets:** some steps produce passwords or keys. Save each one in a password manager the moment you see it.
  Never paste them into the project, a spec file, or a chat with the agents.

---

## Words you'll see

| Word | What it means here |
|---|---|
| **WSL2 / Ubuntu** | A Linux system that runs inside Windows. Your project and the agents live here. |
| **Sandbox** | Claude Code's safety fence around everything the agents run. |
| **Repo** (repository) | The project folder, with its full history of changes, tracked by **git**. |
| **GitHub** | A website that stores a copy of your repo online. |
| **Branch** | A separate line of work inside the repo. Agents work on branches; `main` is the approved version. |
| **PR** (pull request) | A request on GitHub to add a branch's changes to `main`. You review it and click Merge. |
| **Token** | A password-like code that lets the agents use GitHub, with limited rights. |
| **AWS / S3 / bucket** | Amazon's cloud storage. A bucket is one storage container. Big files (3D models, videos) live there. |
| **IAM user / access key** | A limited AWS login for the agents, and its password-like key. |
| **DVC** | A tool that stores big files in your bucket and keeps small "pointer" files in git. |
| **Terminal** | A window where you type commands. Paste a command (right-click pastes), then press **Enter**. |
| **ComfyUI** | The AI image/video app on your PC that makes reference videos. |

### The two terminals

| Name in this guide | How to open it | What the prompt looks like |
|---|---|---|
| **PowerShell** | Start menu → type `PowerShell` → right-click **Windows PowerShell** → **Run as administrator** | `PS C:\...>` |
| **Ubuntu terminal** | Start menu → type `Ubuntu` → click it | `yourname@PC:~$` |

Setup (Parts A to F) uses the Ubuntu terminal for Linux installs. Day to day you can start everything from
PowerShell or a desktop shortcut (Part I).

**Claude must always run inside Ubuntu.** The sandbox only exists there. Never start Claude from a plain
PowerShell or Windows Command Prompt: a Windows copy of Claude Code runs with no sandbox at all. (Tip: Windows
Terminal can show PowerShell and Ubuntu as tabs in one window.)

### Opening project files in Windows

To see your project in File Explorer, click the address bar, type `\\wsl.localhost\Ubuntu-24.04\home\` and press
Enter, then open your Ubuntu username folder and then `game`. (If that doesn't open, type `\\wsl.localhost\` and
use the Ubuntu folder you see there.) Open `.md` files with **Notepad** (right-click → Open with →
Notepad).

---

## Part A: Prepare Windows and Ubuntu

### A1. Check your Windows version
- [ ] Press **Win + R**, type `winver`, press Enter. You need **Windows 11, version 22H2 or newer** (for the
      networking setting in A3). If you're on Windows 10, stop and ask Claude for an alternative.

### A2. Update the NVIDIA driver
- [ ] Open the **NVIDIA App** (Start menu → `NVIDIA`; download it from nvidia.com if missing) → **Drivers** →
      install the newest **Game Ready** or **Studio** driver → restart if asked.

ComfyUI and your own game previews use the GPU. (The agents' sandbox can't see the GPU; that's expected.)

### A3. Install WSL2 and Ubuntu, and share "localhost" with Windows
- [ ] In **PowerShell (as administrator)**: `wsl --install -d Ubuntu-24.04`
- [ ] Restart the PC when told to. After restart an Ubuntu window opens and asks for a **username** and
      **password**. Choose simple ones and save them. (The password doesn't show while you type; that's normal.)
- [ ] In PowerShell: `wsl --update`
- [ ] Make Ubuntu and Windows share `localhost` (so the agents can reach ComfyUI). In PowerShell:
  ```
  notepad $env:USERPROFILE\.wslconfig
  ```
  If Notepad asks to create the file, click **Yes**. Paste these two lines, save, close Notepad:
  ```
  [wsl2]
  networkingMode=mirrored
  ```
- [ ] In PowerShell: `wsl --shutdown` (Ubuntu restarts with the new setting next time you open it).

**Check:** in PowerShell, `wsl -l -v` shows your Ubuntu with **VERSION 2**.

### A4. Install the Ubuntu tools
Open the **Ubuntu terminal** and paste this (it asks for your Ubuntu password and takes a few minutes):
```
sudo apt update && sudo apt install -y git python3 pipx unzip curl ffmpeg xvfb mesa-vulkan-drivers libgl1-mesa-dri \
  bubblewrap socat gh libxi6 libxkbcommon0 libxrender1 libxfixes3 libxxf86vm1 libsm6 libice6 libegl1 libgl1
pipx install "dvc[s3]" && pipx ensurepath
```
Close the Ubuntu terminal and open it again (so the new tools are found).

- [ ] **Check the sandbox can work:** run `sysctl kernel.apparmor_restrict_unprivileged_userns`.
      If it prints `= 1`, ask Claude for the "bwrap AppArmor profile" step from Claude Code's sandboxing docs.
      If it prints `= 0` or an error saying the key doesn't exist, you're fine.

### A5. Choose your Godot version and install Blender and Godot in Ubuntu
Why again, if you already have them on Windows? Your Windows copies are Windows programs (`.exe`); the sandbox
runs Linux and needs the Linux builds of the same apps. And the agents must not use your Windows copies:
Windows programs launched from Ubuntu run outside the sandbox with your full access. This is a one-time
download of about 400 MB. **Keep your Windows Blender as it is.**

- [ ] **Pick one Godot 4.x version** (the newest stable is usually right). You must use this exact version
      everywhere: in Ubuntu, on Windows, and later on the Mac.
- [ ] In your Windows browser, download from the official sites into your **Downloads** folder:
  - **Blender for Linux** (blender.org → Download → choose **Linux**; a `.tar.xz` file)
  - **Godot for Linux** (godotengine.org → Download → Linux → **Godot Engine** standard, not .NET; a `.zip`)
  - **Godot for Windows**, same version, only if you don't already have exactly that version on Windows
    (you'll use it to play the game; a `.zip`)
- [ ] In the **Ubuntu terminal**, replace `YOUR-WINDOWS-NAME` with your Windows user folder name:
  ```
  mkdir -p ~/tools && cd ~/tools
  tar -xf /mnt/c/Users/YOUR-WINDOWS-NAME/Downloads/blender-*-linux-x64.tar.xz
  unzip -o /mnt/c/Users/YOUR-WINDOWS-NAME/Downloads/Godot_v*_linux.x86_64.zip
  sudo ln -sf ~/tools/blender-*-linux-x64/blender /usr/local/bin/blender
  sudo ln -sf ~/tools/Godot_v*_linux.x86_64 /usr/local/bin/godot
  cd ~
  ```
- [ ] If you downloaded the **Windows** Godot zip, unzip it anywhere on Windows (e.g. `C:\Tools\Godot`). There's no installer.

**Check:** `blender --version | head -1` and `godot --version` each print a version.

### A6. Install Claude Code in Ubuntu
- [ ] In the **Ubuntu terminal**: `curl -fsSL https://claude.ai/install.sh | bash`
- [ ] Close and reopen the Ubuntu terminal, then `claude --version`. It must be **2.1.295 or newer**.
- [ ] Run `claude` once, follow the sign-in steps, then type `/exit`.

### A7. Optional extra lock: stop Ubuntu from launching Windows programs
The sandbox already blocks the agents from reaching Windows programs. This adds a second lock that works even
if the sandbox were somehow misconfigured. Side effects: Ubuntu can no longer open Windows apps for you (for
example, sign-in links are shown for you to copy into your browser instead of opening it). Your own access is
unaffected: File Explorer still opens the project, PowerShell can still start Ubuntu, and Part I works as written.
- [ ] Do A6 (signing in to Claude) first. Then in the **Ubuntu terminal**:
  ```
  printf '\n[interop]\nenabled=false\nappendWindowsPath=false\n' | sudo tee -a /etc/wsl.conf
  ```
- [ ] In **PowerShell**: `wsl --shutdown`, then reopen the Ubuntu terminal.
- [ ] **Check:** in the Ubuntu terminal, `cmd.exe /c echo hi` should now fail (e.g. "cannot execute binary file"
      or "not found"). To undo later: `sudo nano /etc/wsl.conf`, delete those three lines, save, `wsl --shutdown`.

---

## Part B: GitHub

### B1. Create the game repo
- [ ] Sign in at github.com (create an account if needed).
- [ ] Top-right **+** → **New repository** → **Repository name:** e.g. `my-game` → **Private**.
- [ ] Leave **Add a README**, **.gitignore** and **license** all **off** → **Create repository**.
- [ ] Save the page's address (like `https://github.com/yourname/my-game`).

### B2. Create the agents' token (a limited GitHub password)
- [ ] Profile picture (top right) → **Settings** → bottom of left menu → **Developer settings** →
      **Personal access tokens** → **Fine-grained tokens** → **Generate new token**.
- [ ] **Token name:** `game-agent`. **Expiration:** 90 days.
- [ ] **Repository access:** **Only select repositories** → `my-game`.
- [ ] **Permissions** → **Repository permissions**: **Contents** = **Read and write**, **Pull requests** =
      **Read and write**. Everything else stays **No access**.
- [ ] **Generate token** → copy it (shown only once) → save it in your password manager.

### B3. Give the token to Ubuntu
In the **Ubuntu terminal**:
```
gh auth login
```
Answer: **GitHub.com** → **HTTPS** → when asked how to authenticate, choose **Paste an authentication token** →
paste the token from B2 → Enter. Then:
```
gh auth setup-git
git config --global user.name "game-agent"
git config --global user.email "game-agent@users.noreply.github.com"
```

---

## Part C: AWS storage for big files

### C1. Create the bucket
- [ ] AWS console (aws.amazon.com → **Sign in**) → top-right region menu → **US East (Ohio) us-east-2**.
- [ ] Search bar → `S3` → **Create bucket**.
- [ ] **Bucket name:** unique, lowercase, e.g. `yourname-mygame-assets`. Save the name.
- [ ] **Block all public access:** leave **ticked**. **Bucket Versioning:** **Enable**. → **Create bucket**.

### C2. Create the agents' limited AWS user
- [ ] Search bar → `IAM` → left menu **Users** → **Create user** → **User name:** `game-dvc`, no console
      access → **Next** → **Attach policies directly**, select nothing → **Next** → **Create user**.
- [ ] Open `game-dvc` → **Permissions** tab → **Add permissions** → **Create inline policy** → **JSON**.
      Replace everything with this, changing **both** `YOUR-BUCKET` to your bucket name:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    { "Effect": "Allow", "Action": "s3:ListBucket", "Resource": "arn:aws:s3:::YOUR-BUCKET" },
    { "Effect": "Allow", "Action": ["s3:GetObject", "s3:PutObject", "s3:AbortMultipartUpload"],
      "Resource": "arn:aws:s3:::YOUR-BUCKET/dvc/*" }
  ]
}
```
- [ ] **Next** → **Policy name:** `game-dvc-bucket` → **Create policy**.

### C3. Create its access key
- [ ] On `game-dvc` → **Security credentials** tab → **Access keys** → **Create access key** →
      **Application running outside AWS** → **Next** → **Create access key**.
- [ ] Save the **Access key ID** and **Secret access key** (shown only once).

### C4. Put the keys in Ubuntu
In the **Ubuntu terminal**:
```
mkdir -p ~/.aws && chmod 700 ~/.aws
nano ~/.aws/credentials
```
Type this with your real values, then save (**Ctrl+O**, **Enter**) and exit (**Ctrl+X**):
```
[game-dvc]
aws_access_key_id = YOUR-ACCESS-KEY-ID
aws_secret_access_key = YOUR-SECRET-ACCESS-KEY
```
Then:
```
printf '[profile game-dvc]\nregion = us-east-2\n' > ~/.aws/config
chmod 600 ~/.aws/credentials ~/.aws/config
```
Only ever put these limited keys here, never your personal AWS keys: the agents can read this folder.

---

## Part D: ComfyUI

- [ ] Start ComfyUI on Windows the way you normally do, and run your reference-to-video workflow once by hand.
- [ ] **Check Ubuntu can reach it:** in the **Ubuntu terminal**, `curl -s http://localhost:8188/system_stats | head -c 200`
      should print some text starting with `{`. If it doesn't: make sure ComfyUI is running, and that A3's
      `networkingMode=mirrored` step was done (then `wsl --shutdown` in PowerShell and reopen Ubuntu).
- [ ] Export the workflow for the agents: in ComfyUI, **Workflow** → **Export (API)** → save as
      `ref_to_video.json` in Downloads. It must be the **API** export, not the normal save. (You'll hand it over in H2.)
- [ ] **Video memory is shared** (8 GB). While the agents make reference videos, don't play the game or use
      Blender on Windows.

---

## Part E: Create the project

In the **Ubuntu terminal** (replace `YOUR-WINDOWS-NAME`):
```
mkdir -p ~/game && cd ~/game
unzip /mnt/c/Users/YOUR-WINDOWS-NAME/Downloads/gamedev-kit.zip
ls
```
You should see `SETUP.md`, `README.md`, `CLAUDE.md` and folders like `docs` and `tools`.

- [ ] Open `docs\specs\PLATFORM.md` in Notepad (see "Opening project files in Windows"). Fill in
      **Orientation** (portrait or landscape) and **Target frame rate** (30 or 60). Save.

---

## Part F: First setup run

### F1. Run the setup script
In the **Ubuntu terminal** (replace `YOUR-BUCKET` with your bucket name; paste all five lines):
```
cd ~/game
export DVC_REMOTE_URL=s3://YOUR-BUCKET/dvc
export DVC_REMOTE_REGION=us-east-2
export DVC_REMOTE_PROFILE=game-dvc
sh tools/setup.sh
```
Running it again later is safe: it skips what's already done.
- [ ] Every line starting with `PASS` must say PASS. Any `FAIL` or `MISSING`: stop and ask Claude with a screenshot.
- [ ] It prints `sandbox network: allowed YOUR-BUCKET.s3.us-east-2.amazonaws.com`.
- [ ] The **Environment** report at the end: all tools `ok`, ComfyUI `reachable`, and a Godot **Vulkan** line
      that mentions `lavapipe` (CPU rendering, expected).

### F2. Connect the repo to GitHub
```
git remote add origin https://github.com/yourname/my-game.git
```

### F3. Test the big-file storage
```
echo test > storage-test.txt && dvc add storage-test.txt && dvc push && echo STORAGE OK
```
- [ ] You should see `STORAGE OK`. Then clean up:
  ```
  dvc remove storage-test.txt.dvc; rm -f storage-test.txt storage-test.txt.dvc; git reset -q; git status --short
  ```
  The last command should print nothing about `storage-test`.

### F4. Start Claude and confirm the protections are on
In the **Ubuntu terminal**, inside `~/game`: run `claude`.
- [ ] It asks whether you trust this folder → **Yes**.
- [ ] If Claude exits with a message about the sandbox not being available: see Troubleshooting.
- [ ] Type `/sandbox` → it should show the sandbox as **enabled** with its dependencies found. Press **Esc**.
- [ ] Type `/hooks` → you should see **PreToolUse**, **PostToolUse**, **Stop** and **SubagentStop**. **Esc**.
- [ ] Paste this to Claude: `Run python3 tools/sandbox_selftest.py and show me the full output.`
      **Every line must say PASS.** If any says FAIL, stop and ask Claude (in the normal app) with a screenshot.

You never had to lock files by hand: the sandbox itself stops the agents' commands from changing the rule files.

---

## Part G: Hand over: the bootstrap

### G1. Run Prompt 1
- [ ] Open `PROMPTS.md`, copy everything inside the **Prompt 1** box, paste it into Claude, press Enter.
- [ ] Answer its questions. At the end it pushes a branch called `arch/bootstrap`.

### G2. Review and merge on GitHub
- [ ] Your repo on github.com → **Pull requests** tab. If there's no PR yet, click the yellow
      **Compare & pull request** banner for `arch/bootstrap` → **Create pull request**.
- [ ] Open the PR → **Files changed** to look through it → **Conversation** tab → **Merge pull request** → **Confirm merge**.

### G3. Protect `main` (approved work only)
- [ ] Repo → **Settings** → **Rules** → **Rulesets** → **New ruleset** → **New branch ruleset**.
- [ ] **Ruleset name:** `protect-main`. **Enforcement status:** **Active**.
- [ ] **Target branches** → **Add target** → **Include default branch**.
- [ ] Tick **Restrict deletions** and **Block force pushes**.
- [ ] Tick **Require a pull request before merging** → **Required approvals:** **0** (GitHub doesn't let you
      approve your own PRs).
- [ ] Tick **Require status checks to pass** → **Add checks** → type `scope` → choose **scope-check**.
- [ ] Leave the **Bypass list** empty → **Create**.

---

## Part H: Tell the agents what to build

You write the specs; the agents handle git for you. Do these when the agents are idle (not mid-task).

### H1. Fill in the specs
- [ ] In Notepad, fill in (following the examples inside):
  `docs\specs\MECHANICS.md` (how the game plays), `docs\specs\ASSETS.md` (every 3D model, and which you'll
  supply yourself), `docs\specs\RIGGING_ANIMATION.md` (which models move, and how).
- [ ] Paste to Claude:
  > I edited docs/specs/MECHANICS.md, ASSETS.md and RIGGING_ANIMATION.md. Commit them on an arch/specs branch,
  > push it, open a pull request, and give me the link. Don't change my text.
- [ ] Merge the PR (as in G2).

### H2. Hand over the ComfyUI workflow
- [ ] In File Explorer, copy `ref_to_video.json` from Downloads into the project's `tools\comfy\workflows\` folder.
- [ ] Paste to Claude:
  > I added my ComfyUI workflow at tools/comfy/workflows/ref_to_video.json. Help me write its .map.json:
  > show me the candidate inputs for the start image, the text prompt, the seed and the video length, and ask
  > me to confirm each. Then commit both files on an arch/comfy-workflow branch, push, open a pull request
  > and give me the link.
- [ ] Merge the PR.

### H3. Hand over models you made yourself (e.g. from Tripo)
- [ ] In File Explorer, create `blender\models\hero\source\` in the project (use your model's id from
      ASSETS.md instead of `hero`) and copy your `.glb` into it as `hero_tripo.glb`.
- [ ] Paste to Claude:
  > I put my own model at blender/models/hero/source/hero_tripo.glb. Create task T000 for the modeler to track
  > it with DVC and commit it unchanged on its task branch, then push and give me the pull request link.
- [ ] Merge the PR.

### H4. Start building
- [ ] Paste **Prompt 2** from `PROMPTS.md`. It plans first and waits for your approval before building anything.

---

## Part I: Day to day

### Starting the agents (every time)
1. Start ComfyUI on Windows (only needed for reference videos).
2. Start Claude in Ubuntu, in your project, with the sandbox. Any one of these:
   - **From PowerShell** (no administrator needed):
     ```
     wsl -d Ubuntu-24.04 --cd ~ -- bash -lc "cd ~/game && claude"
     ```
   - **From the Ubuntu terminal:** `cd ~/game && claude`
   - **Desktop shortcut (double-click):** right-click the desktop → **New** → **Shortcut** → for the location, paste
     `wsl.exe -d Ubuntu-24.04 --cd ~ -- bash -lc "cd ~/game && claude"` → **Next** → name it `Game agents` →
     **Finish**.
3. If Claude ever starts without its sandbox, it refuses to run (that's the `failIfUnavailable` setting), so you
   can't accidentally start it unprotected from these.

### Changing the kit itself (fixes to tools, guards, sandbox settings)
The game agents can't change the kit's rule files, by design. Kit fixes come from a separate **kit-maintenance**
Claude session that runs outside the sandbox in its own copy of the repo:
1. **Ubuntu terminal:** `sh ~/game/tools/maintain.sh` (first time, it makes the copy in `~/kit-maint`).
2. Tell it what's wrong (for example, paste the game agent's report). It fixes it on a `kit/...` branch, runs the
   kit's tests, and opens a pull request. It isn't sandboxed, so stay with it while it works.
3. Review and merge the PR on GitHub. Check its description: it must say whether any protection changed.
4. **Ubuntu terminal** (the agents can't do this part): `cd ~/game && git switch main && git pull`
5. Ask a game agent to run `python3 tools/sandbox_selftest.py`; every line must say PASS.

### Reviewing PRs
Every change reaches `main` only when you merge its PR. On **Files changed**, check the files are where the PR
title says, and read the agent's summary. If something looks wrong, don't merge: tell the agent what to fix.

### Watching gameplay videos (no game code runs on your PC)
At each milestone, QA records short videos of the game being played by its test scripts and tells you which
moments to look at. Videos are just pictures and sound, so watching them is completely safe.
- In File Explorer, open `\\wsl.localhost\Ubuntu-24.04\home\YOUR-UBUNTU-NAME\game\docs\qa\videos\` and double-click
  an `.mp4`; it opens in the Windows video player.
- If a video is missing (shows as a small `.dvc` file only), ask Claude: "run dvc pull for docs/qa/videos".
- The look is the iOS renderer drawn on the CPU; smoothness in the video says nothing about real iPhone speed.

### Playing the game on your PC
Don't open the agents' working folder in Godot: the editor writes files into it and confuses the agents. Play a copy:
1. Make a fresh copy, from **PowerShell**: `wsl -d Ubuntu-24.04 -- bash -lc "rm -rf ~/preview && cp -r ~/game/godot ~/preview"`
   (or in the **Ubuntu terminal**: `rm -rf ~/preview && cp -r ~/game/godot ~/preview`)
2. Open your **Windows Godot** `.exe` → **Import** → browse to
   `\\wsl.localhost\Ubuntu-24.04\home\YOUR-UBUNTU-NAME\preview\project.godot` → **Import & Edit** → press **F5**.

The copy shows whatever the agents have checked out right now; for the approved version, ask the agent to switch
to `main` first. Game scripts run on Windows outside the sandbox, so only play versions you've reviewed.

---

## Part J: The final iPhone build (much later)

When the game is ready, Prompts 4a and 4b in `PROMPTS.md` prepare a package; you build it on a Mac following
the instructions inside (`docs/IOS_HANDOFF.md`). You'll need a Mac with **Xcode**, the **same Godot version** plus
its iOS export templates, and an **Apple Developer** account.

---

## Troubleshooting

| Problem | What to do |
|---|---|
| Claude exits saying the sandbox isn't available | Check `wsl -l -v` says VERSION 2; reinstall `bubblewrap socat` (A4); check the AppArmor step in A4. |
| `sandbox_selftest.py` shows FAIL | Don't start work. Screenshot it and ask Claude (normal app). |
| A setup line says `FAIL` or `MISSING` | Don't continue. Screenshot it and ask Claude. |
| Setup says "No DVC remote configured" | The settings didn't reach the script. Use the five-line form in F1 (with `export`) and run it again. |
| `dvc push` says access denied | Check the bucket name in the policy (C2) and the keys (C4). |
| ComfyUI not reachable | ComfyUI running? `networkingMode=mirrored` set (A3)? Then `wsl --shutdown` and reopen Ubuntu. |
| The agent says a hook or the sandbox blocked it | The guard rails working. Read its explanation; usually the task needs a different agent or your approval. |
| The agent says "working tree has uncommitted changes" | Ask it: "show me git status and explain each change". |
| GitHub refuses pushes (token expired) | Make a new token (B2) and run `gh auth login` again (B3). |
| Godot screenshots say "NO Vulkan driver" | `sudo apt install -y mesa-vulkan-drivers` (A4). |
| The shortcut or PowerShell line says `claude: command not found` | Open the Ubuntu terminal once and run `claude --version`; if that works, close all windows and try again. Check the distro name with `wsl -l -v` and use it instead of `Ubuntu-24.04`. |

## Never give the agents
Your own GitHub or AWS login, admin tokens, SSH keys, your Windows or Ubuntu password, or the ability to change
where git and DVC store things. Don't turn the sandbox off, and don't run Claude with `--dangerously-skip-permissions`.
