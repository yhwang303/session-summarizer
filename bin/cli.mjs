#!/usr/bin/env node
/**
 * session-summarizer CLI
 *
 * Subcommands:
 *   install [--target k1,k2] [--dry-run] [--force]
 *   uninstall [--target k1,k2] [--dry-run]
 *   status
 *   doctor
 *   --help
 */
import { install, uninstall, status, planContext } from "../lib/installer.mjs";
import { detectPython } from "../lib/python.mjs";

const HELP = `session-summarizer — auto-summarize your AI coding session with Anthropic's 9-section template.

Usage:
  npx @joeseesun/session-summarizer <command> [options]

Commands:
  install     Install slash command + PreCompact hook into all detected IDEs.
  uninstall   Remove everything session-summarizer installed. Non-destructive to
              other hooks.
  status      Print what's currently installed where.
  doctor      Print environment diagnostics (Python detection, package layout).

Options:
  --target <keys>   Comma-separated IDE keys. Default: all.
                    Keys: claude-code, cursor, codebuddy, workbuddy, codex
  --dry-run         Print the plan without touching disk.
  --force           Overwrite existing slash-command files on install.
  --json            Emit machine-readable JSON.
  -h, --help        Show this help.
`;

function parseArgs(argv) {
  const args = { _: [], target: null, dryRun: false, force: false, json: false, help: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--dry-run") args.dryRun = true;
    else if (a === "--force") args.force = true;
    else if (a === "--json") args.json = true;
    else if (a === "-h" || a === "--help") args.help = true;
    else if (a === "--target") args.target = String(argv[++i] || "").split(",").filter(Boolean);
    else if (a.startsWith("--target=")) args.target = a.slice("--target=".length).split(",").filter(Boolean);
    else args._.push(a);
  }
  return args;
}

function printPlainInstall(result) {
  if (!result.ok) {
    console.error(`✗ ${result.message}`);
    process.exit(2);
  }
  const { targets, python, command, dryRun } = result;
  console.log(dryRun ? "session-summarizer install (dry-run)" : "session-summarizer install");
  console.log(`  python : ${python.version}  (${python.cmd.join(" ")})`);
  console.log(`  command: ${command}`);
  console.log("");
  for (const t of targets) {
    console.log(`[${t.label}]`);
    console.log(`  slash:  ${t.slash.action}  ${t.slash.path || ""}`);
    const h = t.hook;
    if (h.action === "error") {
      console.log(`  hook:   ERROR  ${h.error}`);
    } else if (h.action === "would-merge") {
      console.log(`  hook:   would-merge → ${h.path}  (event: ${h.event})`);
    } else {
      const bak = h.backup ? `  backup=${h.backup}` : "";
      console.log(`  hook:   ${h.action}  ${t.hookFile}${bak}`);
    }
    if (t.note) console.log(`  note:   ${t.note}`);
    console.log("");
  }
  if (dryRun) console.log("(dry-run — no changes made)");
  else console.log("Next: restart each IDE so the hook loads.");
}

function printPlainUninstall(result) {
  console.log(result.dryRun ? "session-summarizer uninstall (dry-run)" : "session-summarizer uninstall");
  for (const t of result.targets) {
    console.log(`[${t.label}]`);
    console.log(`  slash: ${t.slash.action}`);
    const h = t.hook;
    const bak = h.backup ? `  backup=${h.backup}` : "";
    console.log(`  hook:  ${h.action}${h.removed ? ` (removed ${h.removed})` : ""}${bak}`);
    console.log("");
  }
}

function printPlainStatus(result) {
  console.log("session-summarizer status");
  console.log(`  python : ${result.python ? result.python.version : "NOT FOUND"}`);
  console.log("");
  for (const t of result.targets) {
    const scope = t.projectScoped ? " (project-scoped)" : "";
    console.log(`[${t.label}]${scope}`);
    console.log(`  slash: ${t.slashInstalled ? "✓" : "✗"}  ${t.commandFile}`);
    console.log(`  hook:  ${t.hookInstalled ? "✓" : "✗"}  ${t.hookFile}${t.hookNote ? ` (${t.hookNote})` : ""}`);
    console.log("");
  }
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help || args._.length === 0) {
    console.log(HELP);
    return;
  }

  const cmd = args._[0];
  const ctx = planContext({
    cwd: process.cwd(),
    force: args.force,
    dryRun: args.dryRun,
    only: args.target,
  });

  if (cmd === "doctor") {
    const py = detectPython();
    const out = {
      node: process.version,
      platform: process.platform,
      python: py,
      cwd: process.cwd(),
    };
    if (args.json) console.log(JSON.stringify(out, null, 2));
    else {
      console.log("session-summarizer doctor");
      console.log(`  node    : ${out.node}`);
      console.log(`  platform: ${out.platform}`);
      console.log(`  python  : ${py ? `${py.version}  (${py.cmd.join(" ")})` : "NOT FOUND"}`);
      console.log(`  cwd     : ${out.cwd}`);
      if (!py) {
        console.log("");
        console.log("Hook scripts require Python 3.8+. Install from https://python.org");
        process.exit(2);
      }
    }
    return;
  }

  if (cmd === "install") {
    const r = install(ctx);
    if (args.json) console.log(JSON.stringify(r, null, 2));
    else printPlainInstall(r);
    if (!r.ok) process.exit(2);
    return;
  }

  if (cmd === "uninstall") {
    const r = uninstall(ctx);
    if (args.json) console.log(JSON.stringify(r, null, 2));
    else printPlainUninstall(r);
    return;
  }

  if (cmd === "status") {
    const r = status(ctx);
    if (args.json) console.log(JSON.stringify(r, null, 2));
    else printPlainStatus(r);
    return;
  }

  console.error(`Unknown command: ${cmd}`);
  console.error(HELP);
  process.exit(64);
}

main().catch((e) => {
  console.error(`FATAL: ${e.stack || e.message || e}`);
  process.exit(1);
});
