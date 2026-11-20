# Tobi

A Windows desktop IT support agent. It answers questions from real system data, diagnoses problems,
fixes them after the user approves, re-checks the system to prove the fix worked, and opens a ticket
for IT when something is beyond it. By default it uses NVIDIA-hosted Nemotron (free API key in `.env`); set `model.provider: ollama` in
`config.yaml` to keep everything on the machine with a local Ollama model.

**Run it only inside the test VM, never on a real employee machine.**

## Setup

```powershell
# 1. Ollama: one model in memory at a time
setx OLLAMA_MAX_LOADED_MODELS 1
setx OLLAMA_KEEP_ALIVE 30m
ollama pull qwen2.5:7b          # the model named in config.yaml

# 2. Python environment (3.11 or later)
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 3. Check the model answers and see its speed
.\.venv\Scripts\python.exe scripts\check_model.py
```

The browser task uses the Edge that ships with Windows (`browser.channel: msedge`), so
`playwright install chromium` is not needed.

To use `qwen3:8b` instead: `ollama pull qwen3:8b`, then set `model.name: qwen3:8b` and
`model.reasoning: false` in `config.yaml`. No code changes.

## Run

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py        # chat interface, http://localhost:8501
.\.venv\Scripts\python.exe cli.py "Is developer mode on?"  # terminal; add --yes / --no for approvals
.\.venv\Scripts\python.exe -m pytest tests -q             # tests (routing test needs Ollama)
```

Pages in the interface: **Chat**, **Tickets**, **History** (audit trail) and **What I can do**
(every tool with its risk tier). The sidebar has a **Read-only mode** switch (kill switch).

## What it can do

58 tools in 12 specialists. Each tool belongs to exactly one specialist.

| Specialist | Ask it things like | Read-only checks (R0) | Changes (need approval) |
|---|---|---|---|
| Performance | "My computer is slow", "Do I need to restart?", "What is my serial number?" | health, top processes, system info, pending restart, startup items, stopped services, battery | close a process (R1) |
| Storage | "C drive is full", "What is using space?" | disk usage, temp folders, user folder sizes, recycle bin, disk health | clean temp files (R1), clear an app cache (R1), empty recycle bin (R2) |
| Network | "Websites do not open", "Can I reach server X on port 443?", "Is my clock right?" | connection, DNS, IP config, Wi-Fi, port, website, certificate, proxy, VPN, clock, call quality | flush DNS (R1) |
| Settings | "Is developer mode on?", "What is my default browser?", "Turn on dark mode" | read any of 23 settings, read common settings | open a Settings page (R1), switch one of 4 personal preferences (R1) |
| Software | "Is Zoom installed?", "What was installed this week?" | installed programs, recent changes, Windows Update state, approved catalogue | none: installs become a ticket |
| Devices | "Printer not printing", "Headset not working" | printers, print queue, problem devices, devices by kind | clear a print queue (R1) |
| Crash and Error Log | "Which apps crashed?", "Why did it restart?" | recent errors, app crashes, unexpected shutdowns | none |
| Security | "Is my antivirus on?", "Is this link safe?" | antivirus, firewall, recent threats, suspicious-link check | start a quick scan (R1) |
| Account | "Do I have admin rights?", "When does my password expire?" | current user, password info | none: resets become a ticket |
| Knowledge | "How do I connect to the VPN?" | search the Markdown knowledge base in `kb/`, answer with the source | none |
| Service Desk | "I need a new keyboard", "Show my tickets" | list tickets, ticket status | opens tickets |
| Computer Use | "Open Notepad, write my system health and save it" | | Notepad plan, scripted browser task (R1) |

Adding a capability is one decorated function in `tools/`:

```python
@tool("network", R0, "What it does, in words the model can match to a request.",
      params=(Param("host", "str", "hostname"),))
def my_new_check(host: str) -> dict:
    return {"ok": True, ...}        # short JSON, under 1,500 characters
```

The router, planner, policy gate, approval card, audit log and the "What I can do" page pick it up
without further changes.

## How a request flows

```
route -> plan -> run checks -> answer -> policy gate -> approval -> execute -> verify -> report
```

1. **Redact.** Passwords, keys and card numbers pasted into the chat are removed before the model or the log sees them.
2. **R3 check (Python).** Requests for actions the agent must never do itself (password reset, install,
   switch off protection, admin rights, registry, delete user files, read another person's data) are not
   sent to the model. A ticket is opened instead.
3. **Route.** One short model call picks a specialist, or asks one clarifying question.
4. **Plan.** One short model call picks 1 to 4 read-only tools from that specialist's own list.
   If the model's plan stays malformed after two retries, the specialist's default plan is used.
5. **Answer.** One model call answers from the tool output and may pick one fix from the specialist's
   change tools, `escalate` (open a ticket) or `none`.
6. **Policy gate (Python).** Tool ownership, risk tier, argument types, allow-lists, read-only mode and the
   10-calls-per-request limit are checked in code. A prompt is never the safety control.
7. **Approval.** Every change pauses with Approve / Reject and shows what will change and the risk tier.
8. **Verify.** The checks run again and before/after values are shown. A failed or ineffective fix is
   reported as such, is not retried, and gets a ticket with the diagnostics attached.
9. **Audit.** Request, route, plan, every tool call with arguments, blocked actions, approval, result,
   ticket and user feedback go to `data/audit.db`.

## Risk tiers

| Tier | Meaning | Behaviour |
|---|---|---|
| R0 | Read-only | Runs automatically |
| R1 | Low-impact, reversible change | Needs user approval |
| R2 | Medium change, not reversible | Needs user approval, shown with a stronger warning |
| R3 | High impact or irreversible | Never executed. A ticket is opened for IT |

There is no shell tool. PowerShell is only called with fixed scripts; at most one validated argument
is passed through an environment variable, never spliced into the command.

## Coverage of the full capability specification

The specification lists several hundred tools across many company systems. This prototype builds the
part that can run on one machine without those systems, and is honest about the rest.

| Spec section | Status here |
|---|---|
| 1 Intake | Routing, one clarifying question, secret detection, feedback thumbs. Not built: channels other than the web chat and CLI, translation, screenshot/log upload, sentiment |
| 2 Identity and access | Read-only account facts only. Password reset, unlock, MFA, groups, licences, onboarding/offboarding need a directory connector: they become tickets |
| 3 Endpoint diagnostics | Built for Windows: system, processes, disk, battery, event log, crashes, startup, software, devices, network, Wi-Fi, port, certificate, proxy, VPN, clock, call quality. Not built: SMART details, thermal, crash-dump analysis, packet capture, speed test |
| 4 Endpoint remediation | Built: close process, temp cleanup, app cache, recycle bin, DNS flush, print queue, personal preferences, quick scan. Not built (need admin rights or are R3): service restart, driver/BIOS, registry fixes, restore points, reboot, Office/Outlook repair, macOS/Linux/mobile |
| 5 Software and patching | Read-only inventory, recent changes, update state, approved catalogue. Installs and patches become tickets (need MDM) |
| 6 Asset lifecycle | Not built (needs MDM/CMDB). Model, serial and OS are readable |
| 7 Ticketing | Built-in SQLite ticket desk with context package and status. Not built: ITSM connectors, SLA, approvals, change management |
| 8 Knowledge and memory | Keyword search over `kb/*.md` with sources. Not built: vector search, per-user memory, learning loop |
| 9 Security | Antivirus, firewall, threats, link heuristics, quick scan, secret redaction. Not built: EDR, host isolation, mailbox purge, SIEM export |
| 10 Cloud and email admin | Not built (needs Microsoft 365 / Google Workspace admin connectors) |
| 11 Computer use | Control by accessibility name (Pywinauto) for allowed apps, one scripted browser task, plan approved as a whole. Not built: screenshot/vision control, remote sessions, recording |
| 12 Proactive monitoring | Not built |
| 13 Platform | Built: tool registry with tiers, policy gate, approval gate, audit log, read-only kill switch, tool budget, timeouts, prompt-injection rule (tool output is data). Not built: identity verification, rollback manager, dry-run, PII masking beyond secrets, multi-tenant |

The `connectors:` block in `config.yaml` lists the company systems that are not connected.
The `kb/` articles and the approved software list are sample content: replace them with real ones.

## Demo notes

- "My computer is slow" proposes closing the largest process that is **not** protected. Open a
  memory-heavy app you are happy to lose first, or add names to `performance.protected_processes`.
- The Notepad task pastes text, so the clipboard is used for a moment and then restored. Do not touch
  the mouse or keyboard while it runs.
- Each request makes three model calls (route, plan, answer). On CPU that is one to three minutes.
- `ipconfig /flushdns` needs elevation on some builds; the tool falls back to `Clear-DnsClientCache`.
- If ping is blocked (common on cloud VMs) but the test website opens, ping is reported as unavailable
  rather than the gateway as down.
- Several Windows facts need admin rights (for example Defender details on managed PCs). The tool then
  says "unknown" instead of guessing.


## Models

`config.yaml` -> `model.provider`: `nvidia` (default) or `ollama`.

- NVIDIA: put `NVIDIA_API_KEY=nvapi-...` in `.env` (git-ignored, never in code). Default model
  `nvidia/nemotron-3-ultra-550b-a55b`, with `nvidia/nemotron-3.5-super-vl-120b-a12b` as the backup and the local model
  as the last fallback. Kimi (`moonshotai/kimi-k3.1-pro`) works with the same key: put it in `model.nvidia.name`.
- Prompts sent to the cloud have passwords, tokens and keys removed first, but they do include the request text and
  tool results (system data). Use `ollama` when that must not leave the machine.

## Agents, connectors and Autopilot

The **Agents and connectors** page lists every sub-agent (specialists, ticket desk, web, files, PowerShell, mail,
Intune, Defender ...), each connector with its status (ready / needs setup / switched off), and every tool.

- Switch a connector on in `config.yaml` under `connectors:`; put its credentials in `.env`:
  - Microsoft 365 / Intune / Defender: `M365_CLIENT_ID` (+ `M365_TENANT_ID`), a public-client Entra app with the Graph
    permissions listed in `config.yaml`. Sign-in uses the device-code flow with your own account; the refresh token is
    kept encrypted with Windows DPAPI.
  - ServiceNow: `SERVICENOW_INSTANCE`, `SERVICENOW_USER`, `SERVICENOW_PASSWORD`.
  - Files: folders listed in `connectors.files.folders`. PowerShell: every command needs approval and passes a deny-list.
- **Autopilot** (sidebar toggle, or `python cli.py --auto "..."`) is the general agent: plan, act, check, repeat across all
  ready connectors, up to `autopilot.max_steps`. Read-only tools run at once; every change asks first and shows the exact
  command, file text or email. R3 requests (password resets, security changes, admin rights) are never done by the agent.
- Passwords: Tobi opens your organisation's official self-service reset page (it never resets a password itself).
- Microsoft 365, Intune, Defender and ServiceNow code is tested against mocked responses only, not a live tenant.

## Search agent and Live view

- "Search for a tool called HeyGen and open its website", "open a website called figma", "search the web: clear Teams
  cache": the agent searches the web (Bing, read-only), picks the best match, shows you the address, and opens it in your
  default browser after you approve. Plain searches open the results page (`desktop.search_url` in config.yaml).
- "Open my Downloads folder" opens File Explorer on an allowed folder.
- **Live view** (sidebar toggle, `live_view.enabled` in config.yaml): a panel docked at the bottom of the chat with a
  screenshot taken after each change the agent makes and a timeline of its steps. Screenshots are kept in `data/live`
  (newest 40), stay on this computer and are never sent to the model.

## Printing troubleshooter and troubleshooting knowledge

- Say "my printer is not printing" or "why won't report.pdf print". Tobi checks four layers in one read-only pass: your computer
  (print service, printers, default printer, stuck jobs, driver, recent print errors), the file (missing, empty, locked,
  damaged, password-protected), the printer itself (offline, out of paper or ink, jam, open cover) and the connection
  (network address answers, or USB). Everything wrong on the computer is fixed after one approval (clear queue, set
  default printer, bring online, restart the print service when you are an administrator, test page); everything outside the
  computer gets exact steps for the user; problems that need administrator rights become a ticket. Code: `tools/printing.py`.
- `kb/troubleshooting_*.md` (12 articles: printing, network and VPN, performance, Outlook, Teams and meetings, audio, video and
  display, Windows updates and crashes, accounts, software and Office, files and OneDrive, security, keyboard, mouse and
  power) feed the RAG index. They are written from general Windows and IT knowledge: review them against your own environment.
  Re-index with `python scripts/init_rag.py` (the app also does it at start-up).

## Knowledge: Microsoft Learn library, vector search and general answers

- **Company knowledge base** (`kb/*.md`): your own articles. Most trusted, always cited.
- **Microsoft Learn troubleshooting library** (`kb_vendor/microsoft_learn/`): about 490 Windows troubleshooting
  articles (networking, printing, performance, setup and drivers, Start menu and Explorer, security, sign-in,
  updates, activation, remote desktop...) imported from Microsoft's public repository
  MicrosoftDocs/SupportArticles-docs under CC BY 4.0. Answers cite the original learn.microsoft.com page.
  Refresh or extend it with `python scripts/import_mslearn.py` (`--list` shows the areas, `--areas networking printing`
  imports only some). See `kb_vendor/microsoft_learn/NOTICE.md` for the licence.
- **Vector search**: chunks are embedded with NVIDIA's hosted `nvidia/nemotron-3-embed-1b` model (same
  NVIDIA_API_KEY as the chat model, nothing to install) and combined with keyword (BM25) and exact error-code search.
  Vectors are stored as compact float16. Set `rag.embedding_provider` to `local` (sentence-transformers) or `none`.
- **General-knowledge fallback**: when neither source answers a how-to question (for example "how do I screen
  record?"), Tobi answers from the model's own knowledge and labels it as general guidance. Questions about your
  company's own rules or systems are never guessed: Tobi offers a ticket instead. Turn it off with
  `rag.general_knowledge_fallback: false`.

## Hands-on computer tasks

Tobi does things for you instead of only explaining them. Each change is approved first (Level 1), the live view shows
the steps, and read-only mode blocks them all.

- **Record the screen / take a screenshot**: "record my screen for 5 seconds and save it as demo" saves
  `demo.mp4` in Videos (H.264, no sound, up to 30 s, never overwrites). Screenshots go to Pictures. Tobi uses its own
  bundled recorder (`imageio-ffmpeg`), so it does not depend on Snipping Tool's mouse-driven toolbar; if you ask it to
  open an app first it opens it, then records, and says so. Files stay on your PC and are never sent to the model.
- **Operate an app window**: `list_controls` (real button names), `click_control`, `type_text`, `press_keys`
  (shortcuts such as `ctrl+s` or `win+shift+r`) and `wait_seconds`. Only windows on `desktop.allowed_windows` in
  config.yaml (Notepad, Save as, Calculator, Snipping Tool, Paint by default) can be operated: add more there.
  Shortcuts that lock the PC, close windows, open Run or system menus or end tasks are refused.
  One approval for an app window covers the rest of that task in that window; a recording always asks again.

## Desktop pet and chat window

`start_desktop.bat` (or `python run_desktop.py`, or the Tobi icon) starts Tobi as a small 3D character (the logo, built with three.js: it blinks, follows the mouse, talks while the agent works and shows a red bulb for new answers) at the
bottom-right of the screen, always on top. Click it to open the chat (1/4 of the screen width, up to 3/4 of its
height, rounded corners, just above the avatar); the close button sends the chat back to the avatar, which shows a
red dot when an answer arrived while the chat was closed. No server needs to be started first.
Header icons (top left) open the Agents, Connectors and Tools sheets; the arrow tab on the chat's left edge pulls out
the Live view; the gear holds Autopilot, Live view, Read-only, Open full console (Streamlit, port 8501) and Quit.
Only one copy runs: opening Tobi again opens the chat of the running one, replaces a frozen one, and a watchdog
restarts the app if its window stops answering (for example after the laptop wakes from sleep).
Dev flags: `--open`, `--demo "text"`, `--probe`, `--shot file.png`, `--wait N`.

### Install as an app
`python scripts/install_app.py` puts an **Tobi** icon on the Desktop and in the Start menu (search "Tobi").
Opening it launches the chat window directly, with no console and no web server. `--uninstall` removes the icons.
