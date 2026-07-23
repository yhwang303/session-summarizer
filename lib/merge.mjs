/**
 * Idempotent merge helpers for JSON/TOML hook config files.
 *
 * Strategy:
 * - Never overwrite the whole file. Only touch our own entry.
 * - Each hook we install carries a marker: hooks[].__source === "session-summarizer".
 * - Merge is idempotent: repeated installs replace our marked entry, never
 *   duplicate. Other users' hooks are untouched.
 * - Every write is preceded by a timestamped backup: <file>.bak-<ts>
 */
import { readFileSync, writeFileSync, existsSync, mkdirSync, renameSync, unlinkSync } from "node:fs";
import { dirname } from "node:path";

const MARKER = "session-summarizer";

function timestamp() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}-${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`;
}

function backupFile(path) {
  if (!existsSync(path)) return null;
  const bak = `${path}.bak-${timestamp()}`;
  writeFileSync(bak, readFileSync(path));
  return bak;
}

function atomicWrite(path, content) {
  mkdirSync(dirname(path), { recursive: true });
  const tmp = `${path}.tmp-${process.pid}-${Date.now()}`;
  writeFileSync(tmp, content);
  try {
    renameSync(tmp, path);
  } catch {
    // Rename may fail on some Windows constellations if the target is open in another process.
    // Fall back to overwrite + best-effort tmp cleanup.
    writeFileSync(path, content);
    try { unlinkSync(tmp); } catch { /* ignore */ }
  }
}

/**
 * Merge our PreCompact hook into a Claude-Code-style JSON settings file.
 *
 * Two supported flavors:
 * - "claude" (default): nested {matcher, hooks: [{type,command,timeout}]}
 * - "cursor":            flat  {command, timeout} — no matcher, no wrapping
 *
 * @param {string} filePath
 * @param {{event: string, matcher: string, command: string, timeout: number, flavor?: "claude"|"cursor"}} spec
 * @returns {{action: "created"|"updated"|"unchanged", backup: string|null}}
 */
export function mergeJsonHook(filePath, spec) {
  const flavor = spec.flavor === "cursor" ? "cursor" : "claude";

  let root = {};
  if (existsSync(filePath)) {
    const raw = readFileSync(filePath, "utf8").trim();
    if (raw) {
      try {
        root = JSON.parse(raw);
      } catch (e) {
        throw new Error(`Cannot parse ${filePath} as JSON: ${e.message}`);
      }
    }
  }

  if (typeof root !== "object" || root === null || Array.isArray(root)) {
    throw new Error(`Unexpected root shape in ${filePath}; expected object.`);
  }

  // Cursor's hooks.json also has a top-level "version" field.
  if (flavor === "cursor" && root.version === undefined) {
    root.version = 1;
  }

  root.hooks = root.hooks && typeof root.hooks === "object" ? root.hooks : {};
  const arr = Array.isArray(root.hooks[spec.event]) ? root.hooks[spec.event] : [];

  const desired = flavor === "cursor"
    ? {
        __source: MARKER,
        command: spec.command,
        timeout: Math.min(spec.timeout, 60), // Cursor timeout is seconds, cap at 60
      }
    : {
        __source: MARKER,
        matcher: spec.matcher,
        hooks: [
          {
            type: "command",
            command: spec.command,
            timeout: spec.timeout,
          },
        ],
      };

  const existingIdx = arr.findIndex((e) => e && typeof e === "object" && e.__source === MARKER);
  let action;
  if (existingIdx === -1) {
    arr.push(desired);
    action = "created";
  } else {
    const prev = JSON.stringify(arr[existingIdx]);
    arr[existingIdx] = desired;
    action = prev === JSON.stringify(desired) ? "unchanged" : "updated";
  }
  root.hooks[spec.event] = arr;

  if (action === "unchanged" && existsSync(filePath)) {
    return { action, backup: null };
  }

  const backup = backupFile(filePath);
  atomicWrite(filePath, JSON.stringify(root, null, 2) + "\n");
  return { action, backup };
}

/**
 * Remove our marked entry from a JSON settings file.
 * Returns { action, backup, removed }.
 */
export function unmergeJsonHook(filePath, event) {
  if (!existsSync(filePath)) return { action: "absent", backup: null, removed: 0 };
  const raw = readFileSync(filePath, "utf8").trim();
  if (!raw) return { action: "empty", backup: null, removed: 0 };

  const root = JSON.parse(raw);
  if (!root?.hooks?.[event] || !Array.isArray(root.hooks[event])) {
    return { action: "not-present", backup: null, removed: 0 };
  }
  const before = root.hooks[event].length;
  root.hooks[event] = root.hooks[event].filter(
    (e) => !(e && typeof e === "object" && e.__source === MARKER),
  );
  const removed = before - root.hooks[event].length;
  if (removed === 0) return { action: "not-present", backup: null, removed: 0 };

  if (root.hooks[event].length === 0) delete root.hooks[event];
  if (Object.keys(root.hooks).length === 0) delete root.hooks;

  const backup = backupFile(filePath);
  atomicWrite(filePath, JSON.stringify(root, null, 2) + "\n");
  return { action: "removed", backup, removed };
}

/**
 * TOML merge (Codex config.toml): keep it simple — treat as append-only marked
 * block. Idempotency via `# session-summarizer:BEGIN` / `:END` fences.
 */
const TOML_BEGIN = "# session-summarizer:BEGIN — managed block, do not edit by hand";
const TOML_END = "# session-summarizer:END";

export function mergeTomlHook(filePath, spec) {
  const block = [
    TOML_BEGIN,
    `[[hooks.${spec.event}]]`,
    `matcher = "${spec.matcher}"`,
    `timeout = ${spec.timeout}`,
    `type = "command"`,
    `command = ${JSON.stringify(spec.command)}`,
    TOML_END,
    "",
  ].join("\n");

  let existing = "";
  if (existsSync(filePath)) existing = readFileSync(filePath, "utf8");

  const fenceRegex = new RegExp(
    `${escapeRegex(TOML_BEGIN)}[\\s\\S]*?${escapeRegex(TOML_END)}\\n?`,
    "m",
  );

  let action;
  let next;
  if (fenceRegex.test(existing)) {
    next = existing.replace(fenceRegex, block);
    action = existing === next ? "unchanged" : "updated";
  } else {
    next = existing.endsWith("\n") || existing === "" ? existing + "\n" + block : existing + "\n\n" + block;
    action = "created";
  }

  if (action === "unchanged" && existsSync(filePath)) {
    return { action, backup: null };
  }

  const backup = backupFile(filePath);
  atomicWrite(filePath, next);
  return { action, backup };
}

export function unmergeTomlHook(filePath) {
  if (!existsSync(filePath)) return { action: "absent", backup: null };
  const existing = readFileSync(filePath, "utf8");
  const fenceRegex = new RegExp(
    `\\n?${escapeRegex(TOML_BEGIN)}[\\s\\S]*?${escapeRegex(TOML_END)}\\n?`,
    "m",
  );
  if (!fenceRegex.test(existing)) return { action: "not-present", backup: null };
  const next = existing.replace(fenceRegex, "\n");
  const backup = backupFile(filePath);
  atomicWrite(filePath, next);
  return { action: "removed", backup };
}

function escapeRegex(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
