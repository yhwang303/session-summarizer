/** IDE target metadata — the only place hard-coded per-IDE knowledge lives. */
import { homedir } from "node:os";
import { join } from "node:path";

const HOME = homedir();

/**
 * @typedef {Object} IDETarget
 * @property {string} key
 * @property {string} label
 * @property {string} commandsDir       Where to drop the slash-command markdown.
 * @property {string} commandFilename   Filename inside commandsDir.
 * @property {string} hookFile          Absolute path to hook config file.
 * @property {"json"|"toml"} hookFormat
 * @property {string} hookEvent         Event name inside `hooks.<event>` (Claude spec is PreCompact; Cursor uses camelCase).
 * @property {boolean} projectScoped    True if the config path is project-local rather than in $HOME.
 * @property {string} [note]            Optional install-time note (e.g. Codex trust reminder).
 */

/** @returns {IDETarget[]} */
export function allTargets(cwd = process.cwd()) {
  return [
    {
      key: "claude-code",
      label: "Claude Code",
      commandsDir: join(HOME, ".claude", "commands"),
      commandFilename: "session-summarizer.md",
      hookFile: join(HOME, ".claude", "settings.json"),
      hookFormat: "json",
      hookEvent: "PreCompact",
      projectScoped: false,
    },
    {
      key: "claude-internal",
      label: "Claude Internal (腾讯套壳版)",
      commandsDir: join(HOME, ".claude-internal", "commands"),
      commandFilename: "session-summarizer.md",
      hookFile: join(HOME, ".claude-internal", "settings.json"),
      hookFormat: "json",
      hookEvent: "PreCompact",
      projectScoped: false,
      note: "Tencent's Claude Code-compatible IDE. Same spec as Claude Code, separate home dir.",
    },
    {
      key: "cursor",
      label: "Cursor",
      commandsDir: join(HOME, ".cursor", "skills", "session-summarizer"),
      commandFilename: "SKILL.md",
      hookFile: join(HOME, ".cursor", "hooks.json"),
      hookFormat: "json",
      hookFlavor: "cursor",
      hookEvent: "preCompact",
      hookCommandExtraArgs: ["--host", "cursor"],
      projectScoped: false,
      note: "Cursor's preCompact hook is observe-only (cannot block compaction). Installer wires a nudge that reminds you to run /session-summarizer manually; the slash command itself does the real summarization. Requires Cursor version with preCompact support.",
    },
    {
      key: "codebuddy",
      label: "CodeBuddy",
      commandsDir: join(HOME, ".codebuddy", "commands"),
      commandFilename: "session-summarizer.md",
      hookFile: join(HOME, ".codebuddy", "settings.json"),
      hookFormat: "json",
      hookEvent: "PreCompact",
      projectScoped: false,
    },
    {
      key: "workbuddy",
      label: "WorkBuddy",
      commandsDir: join(HOME, ".workbuddy", "commands"),
      commandFilename: "session-summarizer.md",
      hookFile: join(HOME, ".workbuddy", "settings.json"),
      hookFormat: "json",
      hookEvent: "PreCompact",
      projectScoped: false,
    },
    {
      key: "codex",
      label: "Codex Desktop",
      commandsDir: join(HOME, ".codex", "skills", "session-summarizer"),
      commandFilename: "SKILL.md",
      hookFile: join(HOME, ".codex", "hooks.json"),
      hookFormat: "json",
      hookEvent: "PreCompact",
      projectScoped: false,
      note: "First launch after install: open the /hooks panel in Codex and trust the script.",
    },
  ];
}
