/** Detect a usable Python 3 interpreter on the host. */
import { spawnSync } from "node:child_process";

const CANDIDATES = process.platform === "win32"
  ? ["python", "py -3", "python3"]
  : ["python3", "python"];

/** @returns {{cmd: string[], version: string} | null} */
export function detectPython() {
  for (const spec of CANDIDATES) {
    const parts = spec.split(" ");
    const cmd = parts[0];
    const args = [...parts.slice(1), "-c", "import sys; print(sys.version_info[0])"];
    let r;
    try {
      r = spawnSync(cmd, args, { encoding: "utf8", timeout: 5000 });
    } catch {
      continue;
    }
    if (r.status !== 0 || !r.stdout) continue;
    const major = parseInt(r.stdout.trim(), 10);
    if (major !== 3) continue;

    // Also grab full version string for reporting.
    const v = spawnSync(cmd, [...parts.slice(1), "--version"], { encoding: "utf8", timeout: 5000 });
    return {
      cmd: parts,
      version: (v.stdout || v.stderr || "").trim() || "python3",
    };
  }
  return null;
}

/** Build the shell-safe command string that gets embedded into hook config. */
export function pythonCommandString(python, scriptPath) {
  // Windows CMD needs double-quoted paths; other shells accept single quotes.
  const quote = process.platform === "win32" ? '"' : '"';
  const py = python.cmd.map((x) => (x.includes(" ") ? `"${x}"` : x)).join(" ");
  return `${py} ${quote}${scriptPath}${quote}`;
}
