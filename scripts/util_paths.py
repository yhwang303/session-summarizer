"""统一路径工具：项目根定位、slug 生成、文件名组装、frontmatter 组装。"""
from __future__ import annotations

import datetime as _dt
import os
import re
import subprocess
from pathlib import Path


PROJECT_MARKERS = (".git", ".hg", ".svn", "pyproject.toml", "package.json", "Cargo.toml")
SESSIONS_SUBDIR = Path(".claude") / "sessions"


def locate_project_root(cwd: str | os.PathLike) -> Path:
    """先试 git，再往上找项目标记，都没有就返回 cwd 本身。"""
    cwd_path = Path(cwd).resolve()

    try:
        result = subprocess.run(
            ["git", "-C", str(cwd_path), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip()).resolve()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    p = cwd_path
    for _ in range(20):
        if any((p / m).exists() for m in PROJECT_MARKERS):
            return p
        if p.parent == p:
            break
        p = p.parent

    return cwd_path


def sessions_dir(project_root: Path) -> Path:
    d = project_root / SESSIONS_SUBDIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def build_filename(
    project_root: Path,
    ide: str,
    now: _dt.datetime | None = None,
) -> Path:
    """`YYYY-MM-DD-<ide>-HHMM.md`; collisions get -r2/-r3 suffix.

    No slug from user content — filename carries only unambiguous, stable
    facts: the date, which IDE triggered it, and the minute-precision time.
    Same-day / same-IDE / same-minute collisions (rare) fall back to -rN.
    """
    now = now or _dt.datetime.now()
    date = now.strftime("%Y-%m-%d")
    time_hm = now.strftime("%H%M")
    ide_slug = re.sub(r"[^a-z0-9\-]+", "-", (ide or "unknown").lower()).strip("-") or "unknown"

    base = sessions_dir(project_root) / f"{date}-{ide_slug}-{time_hm}.md"
    if not base.exists():
        return base

    stem = base.stem
    parent = base.parent
    for i in range(2, 100):
        cand = parent / f"{stem}-r{i}.md"
        if not cand.exists():
            return cand
    raise RuntimeError("Too many collisions for %s" % base)


def build_frontmatter(
    session_id: str,
    project_root: Path,
    trigger: str,
    ide: str,
    section_word_count: int,
    pending_count: int,
    now: _dt.datetime | None = None,
) -> str:
    now = now or _dt.datetime.now()
    lines = [
        "---",
        f"session_id: {session_id}",
        f"timestamp: {now.isoformat(timespec='seconds')}",
        f"project: {project_root.as_posix()}",
        f"trigger: {trigger}",
        f"ide: {ide}",
        f"word_count: {section_word_count}",
        f"pending_count: {pending_count}",
        "template: anthropic-nine-section",
        "---",
        "",
    ]
    return "\n".join(lines)


def state_log_path(session_id: str) -> Path:
    """hook 日志目录，跨平台走用户 home。"""
    root = Path.home() / ".claude" / "state" / "session-summarizer"
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{session_id or 'unknown'}.log"


def detect_ide(payload: dict[str, object] | None = None) -> str:
    """尽力从环境变量嗅探 IDE；识别不了就返回 unknown。"""
    env = os.environ
    if env.get("CURSOR_TRACE_ID") or env.get("CURSOR_AGENT"):
        return "cursor"
    if env.get("CODEBUDDY_HOME") or env.get("CODEBUDDY_PROJECT_DIR"):
        return "codebuddy"
    if env.get("WORKBUDDY_HOME") or env.get("WORKBUDDY_PROJECT_DIR"):
        return "workbuddy"
    if env.get("CODEX_HOME") or env.get("CODEX_PROJECT_DIR"):
        return "codex"
    if env.get("CLAUDE_PROJECT_DIR") or env.get("CLAUDECODE"):
        return "claude-code"
    if payload:
        for k in ("ide", "client", "agent_name"):
            v = payload.get(k)
            if isinstance(v, str) and v:
                return v.lower()
    return "unknown"
