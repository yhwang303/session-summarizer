/** Orchestrates install / uninstall / status across all IDE targets. */
import {
  existsSync,
  mkdirSync,
  readFileSync,
  writeFileSync,
  unlinkSync,
  lstatSync,
} from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { allTargets } from "./ide-targets.mjs";
import { detectPython, pythonCommandString } from "./python.mjs";
import { mergeJsonHook, mergeTomlHook, unmergeJsonHook, unmergeTomlHook } from "./merge.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
export const PACKAGE_ROOT = resolve(HERE, "..");
export const HOOK_SCRIPT = join(PACKAGE_ROOT, "scripts", "precompact_hook.py");
export const COMMAND_SRC = join(PACKAGE_ROOT, "commands", "session-summarizer.md");
export const DEFAULT_TIMEOUT_MS = 60000;

function linkOrCopy(src, dst, { force }) {
  if (existsSync(dst)) {
    if (!force) return { action: "skip-exists", path: dst };
    try {
      unlinkSync(dst);
    } catch { /* fall through */ }
  }
  mkdirSync(dirname(dst), { recursive: true });
  // Copy + template-substitute {{PLUGIN_ROOT}} so the slash command works
  // regardless of where the package lives on the user's machine (Windows,
  // macOS, Linux — all get correct absolute paths).
  const rawContent = readFileSync(src, "utf8");
  const posixRoot = PACKAGE_ROOT.replace(/\\/g, "/");
  const rendered = rawContent.replace(/\{\{PLUGIN_ROOT\}\}/g, posixRoot);
  writeFileSync(dst, rendered);
  return { action: "copied", path: dst };
}

function removeCommand(dst) {
  if (!existsSync(dst)) return { action: "absent" };
  try {
    const stat = lstatSync(dst);
    unlinkSync(dst);
    return { action: stat.isSymbolicLink() ? "unlinked-symlink" : "unlinked-file" };
  } catch (e) {
    return { action: "error", error: e.message };
  }
}

export function planContext({ cwd, force = false, dryRun = false, only = null }) {
  const python = detectPython();
  const targets = allTargets(cwd).filter((t) => (only ? only.includes(t.key) : true));
  return { python, targets, force, dryRun, cwd };
}

export function install(ctx) {
  const { python, targets, force, dryRun } = ctx;

  if (!python) {
    return {
      ok: false,
      reason: "python3-not-found",
      message: "No usable Python 3 interpreter found on PATH. Install Python 3.8+ and retry.",
    };
  }
  if (!existsSync(HOOK_SCRIPT)) {
    return {
      ok: false,
      reason: "hook-script-missing",
      message: `Hook script not shipped in package: ${HOOK_SCRIPT}`,
    };
  }
  if (!existsSync(COMMAND_SRC)) {
    return {
      ok: false,
      reason: "command-src-missing",
      message: `Slash command source not shipped in package: ${COMMAND_SRC}`,
    };
  }

  const command = pythonCommandString(python, HOOK_SCRIPT);
  const perTarget = [];

  for (const t of targets) {
    const entry = {
      key: t.key,
      label: t.label,
      commandFile: join(t.commandsDir, t.commandFilename),
      hookFile: t.hookFile,
      note: t.note || null,
    };

    if (dryRun) {
      entry.slash = { action: "would-install", path: entry.commandFile };
      entry.hook = t.hookEvent
        ? {
            action: "would-merge",
            path: t.hookFile,
            command,
            event: t.hookEvent,
          }
        : { action: "skipped-no-precompact-event" };
      perTarget.push(entry);
      continue;
    }

    entry.slash = linkOrCopy(COMMAND_SRC, entry.commandFile, { force });

    if (!t.hookEvent) {
      // Target's host doesn't emit a PreCompact-equivalent event (e.g. Cursor).
      // Skip hook merge — the manual slash command is the only automation path.
      entry.hook = { action: "skipped-no-precompact-event" };
      perTarget.push(entry);
      continue;
    }

    const spec = {
      event: t.hookEvent,
      matcher: "auto",
      command,
      timeout: DEFAULT_TIMEOUT_MS,
    };

    try {
      entry.hook =
        t.hookFormat === "json"
          ? mergeJsonHook(t.hookFile, spec)
          : mergeTomlHook(t.hookFile, spec);
      entry.hook.event = t.hookEvent;
    } catch (e) {
      entry.hook = { action: "error", error: e.message };
    }
    perTarget.push(entry);
  }

  return { ok: true, python, command, targets: perTarget, dryRun };
}

export function uninstall(ctx) {
  const { targets, dryRun } = ctx;
  const perTarget = [];

  for (const t of targets) {
    const entry = { key: t.key, label: t.label };
    const cmdPath = join(t.commandsDir, t.commandFilename);

    if (dryRun) {
      entry.slash = { action: "would-remove", path: cmdPath };
      entry.hook = { action: "would-unmerge", path: t.hookFile };
      perTarget.push(entry);
      continue;
    }

    entry.slash = removeCommand(cmdPath);
    if (!t.hookEvent) {
      entry.hook = { action: "skipped-no-precompact-event" };
      perTarget.push(entry);
      continue;
    }
    try {
      entry.hook =
        t.hookFormat === "json"
          ? unmergeJsonHook(t.hookFile, t.hookEvent)
          : unmergeTomlHook(t.hookFile);
    } catch (e) {
      entry.hook = { action: "error", error: e.message };
    }
    perTarget.push(entry);
  }
  return { ok: true, targets: perTarget, dryRun };
}

export function status(ctx) {
  const { targets, python } = ctx;
  const perTarget = targets.map((t) => {
    const cmdPath = join(t.commandsDir, t.commandFilename);
    const slashInstalled = existsSync(cmdPath);

    let hookInstalled = false;
    let hookNote = null;
    if (!t.hookEvent) {
      hookNote = "no PreCompact event on this host";
    } else if (existsSync(t.hookFile)) {
      try {
        if (t.hookFormat === "json") {
          const raw = readFileSync(t.hookFile, "utf8").trim();
          if (raw) {
            const root = JSON.parse(raw);
            const arr = root?.hooks?.[t.hookEvent];
            hookInstalled = Array.isArray(arr) &&
              arr.some((e) => e && typeof e === "object" && e.__source === "session-summarizer");
          }
        } else {
          const raw = readFileSync(t.hookFile, "utf8");
          hookInstalled = raw.includes("session-summarizer:BEGIN");
        }
      } catch (e) {
        hookNote = `parse error: ${e.message}`;
      }
    }
    return {
      key: t.key,
      label: t.label,
      commandFile: cmdPath,
      slashInstalled,
      hookFile: t.hookFile,
      hookInstalled,
      hookNote,
      projectScoped: t.projectScoped,
    };
  });
  return { python, targets: perTarget };
}
