---
description: Summarize the current session in the 9-section template and persist to <project>/.claude/sessions/
argument-hint: [--dry-run]
allowed-tools: Read, Write, Bash(python:*), Bash(python3:*)
---

Produce a full 9-section summary of the current session and persist it as a resumable markdown file. This lets you switch IDE or start a new session and pick up exactly where you left off.

## Step 1 — Load the template

Use the Read tool on this file and obey every rule in it (especially §6 must preserve user messages verbatim, and §9 must quote the most recent user message):

```
{{PLUGIN_ROOT}}/templates/nine-section-template.md
```

## Step 2 — Produce the 9 sections

Follow the template exactly. **Don't print the sections into chat** — write them straight to a temp `.md` file using the Write tool:

- macOS / Linux: `/tmp/session-summary-<session_id>.md`
- Windows: `%TEMP%\session-summary-<session_id>.md`

Constraints:
- Every `## N. Title / 中文` heading must match the template exactly (validation will reject otherwise)
- §6 keeps every non-tool-result user message verbatim — no rewriting, translating, or merging
- §9 must quote a short excerpt from the most recent user message; if that message doesn't imply a next step, write `awaiting user`
- Never invent tasks the user didn't ask for

## Step 3 — Persist

Call `write_summary.py` to validate + write to disk + update `index.md`. Use whichever Python command exists on this host (`python3` first, then `python`):

```bash
python3 "{{PLUGIN_ROOT}}/scripts/write_summary.py" \
  --session-id "<current session id>" \
  --project "<current project root>" \
  --content "<path to the temp file from step 2>" \
  --trigger manual \
  --ide "<current IDE key, e.g. claude-code|claude-internal|cursor|codebuddy|workbuddy|codex>"
```

If the user passed `--dry-run`, **skip this step**. Instead, print the temp-file path so the user can inspect it themselves.

## Step 4 — Report back

Once persisted, tell the user briefly:
- Written path
- Sections OK (from the `write_summary.py` JSON)
- Pending task count (from §7)
- `index.md` updated

## Arguments

User input: `$ARGUMENTS`. Supported:
- `--dry-run` — skip the persist step

## Project root

Prefer `git rev-parse --show-toplevel`; fall back to the current working directory. The output directory is always `<project-root>/.claude/sessions/` — do not vary by IDE (cross-IDE handoff depends on a stable path).

## Filename

`write_summary.py` builds the filename as `YYYY-MM-DD-<ide>-HHMM.md`. Do not try to override it — collisions inside the same minute get `-r2/-r3` suffixes automatically.
