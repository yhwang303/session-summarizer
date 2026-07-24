# session-summarizer

> Auto-summarize your AI coding session with Anthropic's 9-section template **before** context compaction fires. Cross-IDE, cross-session, zero data loss.

<p>
  <a href="https://github.com/yhwang303/session-summarizer/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT"></a>
  <a href="README.zh-CN.md">简体中文</a>
</p>

**The problem**: When your session hits ~85% context, Claude Code (and every IDE that follows its spec) auto-compacts your history. The default compaction summary is lossy — verbatim user messages, load-bearing code snippets, and half-solved bugs often disappear. If you switch IDE (Claude Code → Cursor → Codex) or open a new session, there's nothing to hand off.

**What this does**: A `PreCompact` hook fires **before** the system compacts. It injects Anthropic's 9-section template (from Claude Code's own `BASE_COMPACT_PROMPT`) into the model's context, so the model writes a full structured summary **first**, saves it to `<project>/summary/sessions/`, then lets compaction proceed.

Works with **Claude Code · Claude Internal · CodeBuddy · WorkBuddy · Codex Desktop · Cursor**.

> ⚠️ **Cursor is a partial case.** Its `preCompact` hook is [documented](https://cursor.com/docs/agent/third-party-hooks) as *observational* — it fires when compaction happens but cannot inject a prompt or block the compaction. So on Cursor, this plugin can only *warn* you (via `user_message`) that compaction is in progress; it cannot auto-write the summary. Run `/session-summarizer` manually at ~60-70% context. See [Cursor limitations](#cursor-limitations-important) below.

---

## IDE support matrix

| IDE | Manual `/session-summarizer` | Auto-triggered summary before compaction |
|---|---|---|
| Claude Code | ✅ | ✅ (real inject) |
| Claude Internal (腾讯) | ✅ | ✅ (real inject) |
| CodeBuddy | ✅ | ✅ (real inject) |
| WorkBuddy | ✅ | ✅ (real inject) |
| Codex Desktop | ✅ | ✅ (real inject; needs `/hooks` trust on first run) |
| **Cursor** | ✅ | ⚠️ **Warn-only** — see below |

---

## Install

Pick the option that matches your setup.

### Option 1 — Claude Code plugin marketplace (recommended for Claude Code users)

Inside Claude Code:

```
/plugin marketplace add yhwang303/session-summarizer
/plugin install session-summarizer@session-summarizer
```

Restart Claude Code. That's it. `/session-summarizer` and the `PreCompact` hook are both live.

### Option 2 — `npx` one-liner (recommended for multi-IDE users)

If you want it in Cursor / CodeBuddy / WorkBuddy / Codex too (or in addition to Claude Code):

```bash
npx github:yhwang303/session-summarizer install
```

Or install into specific IDEs only:

```bash
npx github:yhwang303/session-summarizer install --target claude-code,cursor
```

The installer:

- Drops the `/session-summarizer` slash command into each IDE's commands directory
- Merges a `PreCompact` hook into each IDE's settings file (JSON or TOML)
- Backs every file up as `<file>.bak-<timestamp>` before writing
- Is **idempotent** — re-running never duplicates entries
- Preserves your existing hooks (adds a marked entry, never touches other people's)

Verify:

```bash
npx github:yhwang303/session-summarizer status
```

Uninstall (only removes what session-summarizer added; leaves your other hooks untouched):

```bash
npx github:yhwang303/session-summarizer uninstall
```

### Option 3 — Manual (clone & merge)

For environments where `npx` isn't available:

```bash
git clone https://github.com/yhwang303/session-summarizer ~/session-summarizer
cd ~/session-summarizer
node bin/cli.mjs install
```

**Requirements**: Node 18+ and Python 3.8+ (Python is used by the hook script itself, not by the installer).

---

## How it works

Two triggers, one output shape:

| Trigger | When it fires | How the summary gets written |
|---|---|---|
| **Explicit** | You type `/session-summarizer` any time | Slash command loads the 9-section template and calls `write_summary.py` |
| **Automatic** | `PreCompact` event — right before the IDE auto-compacts | Hook injects the template into `additionalContext`; the model writes it, calls `write_summary.py`, then lets the IDE compact |

Output goes to a consistent path regardless of IDE — that's the whole point:

```
<project>/summary/sessions/
├── index.md                          # append-only, human-readable
├── 2026-07-24-claude-code-1430.md
├── 2026-07-24-codebuddy-1615.md
└── 2026-07-23-cursor-2210.md
```

Every summary follows Claude Code's official `BASE_COMPACT_PROMPT`:

1. **Primary Request and Intent** — every explicit user ask, in order
2. **Key Technical Concepts** — technologies actually discussed
3. **Files and Code Sections** — every file touched, plus load-bearing snippets
4. **Errors and Fixes** — every error and how it was resolved (user's own wording preserved)
5. **Problem Solving** — completed + still-in-progress
6. **All User Messages** — **verbatim**, drift anchor
7. **Pending Tasks** — explicit unfinished asks
8. **Current Work** — what you were doing right before compaction
9. **Optional Next Step** — quoted from the most recent user message

Section 6 is what makes cross-session resumption safe: you can hand a new session the summary file and it can reconstruct your exact ask, not a paraphrase.

---

## Cross-IDE handoff

```
Session A (Claude Code)                    Session B (Cursor / Codex / anything)
─────────────────────                      ───────────────────────────────────
context hits 80% context                       "Read summary/sessions/2026-07-24-*.md
      │                                        and continue where I left off"
      ▼
PreCompact hook fires                                       │
      │                                                     ▼
9-section summary written                          Model picks up with §6
to summary/sessions/                              (verbatim user asks) + §8
      │                                          (what was in flight) + §9
      ▼                                          (next step)
IDE compacts normally
```

The output directory is fixed at `summary/sessions/` **regardless of which IDE triggered it**. That's the design — cross-IDE handoff would be impossible with per-IDE paths.

---

## Commands

```
session-summarizer <command> [options]

  install     Install into all IDEs (default) or --target <keys>
  uninstall   Remove everything session-summarizer added
  status      Show install state per IDE
  doctor      Diagnostics (Node/Python detection, layout)

Options:
  --target claude-code,claude-internal,cursor,codebuddy,workbuddy,codex
  --dry-run          Print plan without touching disk
  --force            Overwrite existing slash-command files
  --json             Machine-readable output
```

---

## Cursor limitations (important)

Cursor is different from every other supported host. **Read this before assuming it works the same way.**

**What Cursor's `preCompact` hook does** (per [official docs](https://cursor.com/docs/agent/third-party-hooks)):
- Fires when auto-compaction happens
- Receives useful stdin fields: `context_usage_percent`, `is_first_compaction`, `messages_to_compact`, etc.
- **Only accepts `user_message` in stdout** — no `additionalContext`, no `decision`, no `block`
- Explicitly documented as: *"an observational hook that cannot block or modify the compaction behavior"*

**What this means for session-summarizer on Cursor**:
- By the time the hook fires, Cursor has *already committed* to compacting — details are being lost right now, not "about to be lost"
- The hook cannot ask the model to write a summary first
- The most we can do is display a `user_message` telling you compaction is happening

**What we do on Cursor**:
- Install the `/session-summarizer` slash command into `~/.cursor/skills/session-summarizer/SKILL.md` for manual use
- Register a `preCompact` hook that emits a `user_message` reminding you to run `/session-summarizer` *earlier* next time (at ~60-70% context) rather than waiting for auto-compaction

**Recommended workflow on Cursor**:
1. Run `/session-summarizer` **proactively** during long sessions — don't wait for the auto-compact warning
2. Watch for the compaction warning message; when you see it, treat the current session as "already lossy" and start recovering with the summary file you wrote earlier
3. For handoff to another IDE, generate the summary via `/session-summarizer` before switching

**Why we didn't build "stop-hook + SQLite polling" auto-injection**:
Cursor's `stop` hook does support a `followup_message` field that could theoretically auto-inject `/session-summarizer` after every N turns. But this would require reading Cursor's undocumented SQLite chat storage (`state.vscdb`, schema is community-reversed) to estimate context usage, which is brittle across Cursor upgrades. If you want that path, open an issue — we can add it as an opt-in flag if there's demand.

**Other hosts** (Claude Code / Claude Internal / CodeBuddy / WorkBuddy / Codex Desktop) don't have this limitation — their `PreCompact` hooks accept `additionalContext` and can genuinely make the model write a summary before compaction proceeds.

---

## Safety guarantees

- **Never destroys your hooks.** Merge appends a marked entry (`__source: "session-summarizer"`); your own hooks stay put.
- **Auto backup** before every write: `<file>.bak-<YYYYMMDD-HHMMSS>`.
- **Idempotent.** Repeated `install` shows `unchanged` — no duplicate entries.
- **Scoped uninstall.** Only removes the marked entry. Everything else you had is preserved.
- **Hook never calls the LLM directly.** It only injects an `additionalContext` string; the current session's model does the writing. Worst case (model ignores it): you fall back to the IDE's default compaction — nothing crashes.

---

## FAQ

**Q: Where do summaries live?**
`<project>/summary/sessions/`. Same path across every IDE — that's what makes cross-IDE handoff possible.

**Q: Should I commit `summary/sessions/` to git?**
Your call. If not, add `summary/sessions/` to `.gitignore` (this repo's `.gitignore` already excludes it).

**Q: Does the hook fire when I manually run `/compact`?**
No. Only on `auto` triggers. Manual compaction means you know what you're doing.

**Q: Does this work with Codex CLI (the terminal one, not the desktop app)?**
No. Codex's Rust CLI doesn't expose user-level hooks. Codex Desktop is supported. CLI users can still run `/session-summarizer` manually.

**Q: Is Cursor's auto-triggered path as good as the others?**
No — see [Cursor limitations](#cursor-limitations-important). On Cursor the hook can only *warn* you, not write the summary. Manual `/session-summarizer` still works exactly like everywhere else. If you use Cursor heavily, get in the habit of running it proactively at ~60-70% context.

**Q: Why not use Cursor's `stop` hook to auto-inject `/session-summarizer` after N turns?**
It's technically possible via `followup_message`, but it requires reading Cursor's undocumented SQLite chat DB to estimate context usage, and the schema breaks on Cursor upgrades. Not shipped by default; open an issue if you want an opt-in flag.

**Q: What if my auto-triggered summary got cut off?**
The hook only injects a *prompt*; the model does the writing. In very tight context conditions, output may be shorter than ideal. Best practice: run `/session-summarizer` manually before you cross ~80% context on long design/debug sessions you plan to resume.

**Q: I want to re-run install after upgrading — safe?**
Yes. Idempotent. Re-run to pick up any new features.

---

## Contributing

Issues and PRs welcome at [github.com/yhwang303/session-summarizer](https://github.com/yhwang303/session-summarizer).

Before opening a PR: run `node bin/cli.mjs install --dry-run` to sanity-check the plan output on your machine.

---

## License

MIT © [yhwang303](https://github.com/yhwang303)
