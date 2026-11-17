# IT Buddy

A Windows desktop IT support agent that diagnoses a computer problem from real system data,
fixes it after the user approves, and re-checks the system to prove the fix worked.
Version 1 is a demo prototype: one Windows VM, a local model through Ollama, no cloud model.

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
`playwright install chromium` is not needed. Set `channel: null` to use bundled Chromium instead.

### Model

`config.yaml` currently uses `qwen2.5:7b` because it was already on this VM and the disk had
too little free space to pull the PRD's `qwen3:8b`. To switch, free disk space, then:

```powershell
ollama pull qwen3:8b
```

and set `model.name: qwen3:8b` and `model.reasoning: false` in `config.yaml`. No code changes.
If the eval rate from `check_model.py` is under 5 tokens per second, use a smaller model.

## Run

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py        # chat interface, http://localhost:8501
.\.venv\Scripts\python.exe cli.py "My C drive is almost full."   # terminal; add --yes / --no
.\.venv\Scripts\python.exe -m pytest tests -q             # tests (routing test needs Ollama)
```

## The five demo scenarios

| # | Say | Fix (needs approval) | Verification |
|---|-----|----------------------|--------------|
| 1 | My computer is very slow. | Close the largest closable process | Memory before and after |
| 2 | My C drive is almost full. | Delete old files in the allowed temp folders | Free space before and after |
| 3 | Wi-Fi is connected but websites do not open. | Flush the DNS cache | DNS and one website re-tested |
| 4 | Open Notepad, write a summary of my system health and save it in Documents. | Notepad plan (6 steps) | The file exists |
| 5 | Open the test portal and download the latest report. | Scripted browser task | The downloaded file exists |

Demo notes:

- Scenario 1 closes the largest process that is **not** on the protected list. Before the demo,
  open a memory-heavy app you are happy to lose (for example a browser with many tabs), so the
  agent does not pick something you need.
- Scenario 3: on a healthy network the agent still offers the flush as a safe first step and the
  before/after shows "works -> works". To show a real failure, break DNS on the VM first.
- Scenario 4: do not touch the mouse or keyboard while Notepad is being driven. Text is pasted,
  so the clipboard is used for a moment and then restored.
- Scenario 5 uses a small local portal served from `test_portal/` on port 8765.

## How it works

```
route -> diagnose -> policy gate -> approval (interrupt) -> execute -> verify -> report
```

- **Router** (`agent/router.py`): one short model call picks Performance, Storage, Network or
  Computer Use, or "none" with a clarifying question.
- **Specialists** (`agent/specialists.py`): each runs its own read-only tools as a fixed plan,
  then makes one model call that writes the diagnosis and picks one fix from its own list.
  Tool arguments (for example which PID to close) are checked against the tool output in Python.
  The Computer Use specialist only picks a predefined task; Python builds the steps.
- **Policy gate** (`safety/policy.py`): Python code, not a prompt. It enforces tool ownership,
  risk levels, the allow-lists in `config.yaml`, the 10 tool calls per request limit, the 30 second
  timeout and the 1,500 character output limit. Level 2 tools cannot run without an approval.
  Level 3 requests (install, passwords, permissions, registry, security settings, deleting user
  files) are refused before the model is called.
- **Approval**: LangGraph `interrupt()` with a SQLite checkpointer. A computer-use task is approved
  as a whole plan. Reject changes nothing and is logged.
- **Verify**: the same diagnostic runs again. If a step failed or the problem remains, the agent
  says so and recommends escalation. It never retries a fix.
- **Audit** (`safety/audit.py`): every request, routing decision, tool call with arguments,
  blocked action, approval decision, result and report goes to `data/audit.db`. The History page
  shows past tasks and their full audit trail.

Model calls per request: two (router + diagnosis). The final report is assembled in Python from
the diagnosis and the measured numbers, so it cannot contain invented data.

## Tool catalogue (14 tools, no shell)

| Agent | Level 1 (automatic) | Level 2 (approval) |
|-------|---------------------|--------------------|
| Performance | `get_system_health`, `get_running_processes` | `close_process(pid)` |
| Storage | `get_disk_usage`, `find_large_temp_folders` | `clean_approved_temp_files()` |
| Network | `check_network_connection`, `check_dns_resolution`, `get_network_config` | `flush_dns_cache()` |
| Computer Use | | `open_application`, `click_control`, `type_text`, `run_browser_task` |

## Things worth knowing

- `clean_approved_temp_files` only deletes files older than `storage.min_file_age_minutes`
  (60 by default), never follows links or junctions out of the folder, and skips files in use.
- `close_process` refuses protected names, IT Buddy's own process tree, other users' processes and
  system processes. Ollama's processes are on the protected list.
- `ipconfig /flushdns` needs an elevated prompt on some Windows builds. The tool then falls back
  to `Clear-DnsClientCache`, which works for a standard user.
- If ping is blocked on the network (common on cloud VMs) but the test website opens, the network
  tool reports ping as unavailable instead of reporting the gateway as down.

## Not in version 1

Remote or multiple machines, ticketing and device-management integrations, logins and roles,
knowledge-base search, installing software or changing security settings, screenshot-based
control, free-form browser tasks (Browser Use), production hardening.
