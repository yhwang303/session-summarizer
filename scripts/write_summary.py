#!/usr/bin/env python3
"""落盘九段式总结、更新 index.md。

由 slash command `/session-summarizer` 或 PreCompact hook 引导的模型调用。
出错返回非零并打印错误到 stderr；日志额外写 ~/.claude/state/session-summarizer/。
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
from pathlib import Path

# Windows 默认 stdout/stderr 常是 gbk，遇到 CJK 文件名/标题会 UnicodeEncodeError。
# 统一强制 utf-8。
for _stream_name in ("stdout", "stderr"):
    _s = getattr(sys, _stream_name)
    try:
        _s.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        setattr(sys, _stream_name, io.TextIOWrapper(_s.buffer, encoding="utf-8", newline=""))

sys.path.insert(0, str(Path(__file__).resolve().parent))
from util_paths import (  # noqa: E402
    build_filename,
    build_frontmatter,
    detect_ide,
    locate_project_root,
    sessions_dir,
    state_log_path,
)


SECTION_HEADERS = [
    "Primary Request and Intent",
    "Key Technical Concepts",
    "Files and Code Sections",
    "Errors and Fixes",
    "Problem Solving",
    "All User Messages",
    "Pending Tasks",
    "Current Work",
    "Optional Next Step",
]

_INDEX_START = "<!-- SESSION_SUMMARIZER_INDEX_START -->"
_INDEX_END = "<!-- SESSION_SUMMARIZER_INDEX_END -->"


def _validate_nine_sections(content: str) -> tuple[bool, list[str]]:
    """校验 9 个段落标题都在，返回 (ok, missing_list)。"""
    missing: list[str] = []
    for idx, name in enumerate(SECTION_HEADERS, start=1):
        pattern = rf"^##\s+{idx}\.\s+{re.escape(name)}\b"
        if not re.search(pattern, content, flags=re.MULTILINE):
            missing.append(f"{idx}. {name}")
    return not missing, missing


def _count_pending(content: str) -> int:
    m = re.search(
        r"^##\s+7\.\s+Pending Tasks[^\n]*\n(.*?)(?=^##\s+8\.\s)",
        content,
        flags=re.MULTILINE | re.DOTALL,
    )
    if not m:
        return 0
    body = m.group(1)
    if "_（无）_" in body or "_(none)_" in body.lower():
        return 0
    return sum(1 for line in body.splitlines() if re.match(r"^\s*[-*]\s+\S", line))


def _update_index(project_root: Path, entry_line: str) -> Path:
    idx_path = sessions_dir(project_root) / "index.md"
    if not idx_path.exists():
        header = (
            "# Session Summaries Index\n\n"
            f"{_INDEX_START}\n\n{_INDEX_END}\n\n"
            "> 本目录由 session-summarizer plugin 维护。"
            f"标记 `{_INDEX_START}` 与 `{_INDEX_END}` 之间的内容会被自动重写；\n"
            "> 之外的内容你可以自由编辑（例如加分类说明）。\n"
        )
        idx_path.write_text(header, encoding="utf-8")

    text = idx_path.read_text(encoding="utf-8")
    if _INDEX_START not in text or _INDEX_END not in text:
        text = text.rstrip() + f"\n\n{_INDEX_START}\n\n{_INDEX_END}\n"

    def _repl(match: re.Match[str]) -> str:
        inner = match.group(1).strip()
        new_lines = [entry_line] + [l for l in inner.splitlines() if l.strip()]
        return f"{_INDEX_START}\n" + "\n".join(new_lines) + f"\n{_INDEX_END}"

    text = re.sub(
        rf"{re.escape(_INDEX_START)}\n(.*?)\n{re.escape(_INDEX_END)}",
        _repl,
        text,
        count=1,
        flags=re.DOTALL,
    )
    idx_path.write_text(text, encoding="utf-8")
    return idx_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Persist a 9-section session summary.")
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--project", required=True, help="Project root or any cwd inside it.")
    parser.add_argument("--content", required=True, help="Path to markdown file with 9 sections.")
    parser.add_argument("--trigger", default="manual", choices=["manual", "auto"])
    parser.add_argument("--ide", default="")
    parser.add_argument("--dry-run", action="store_true")
    # --title kept for backward compat with older slash-command definitions;
    # ignored so filename stays predictable.
    parser.add_argument("--title", default=None, help="(deprecated, ignored)")
    args = parser.parse_args(argv)

    log = state_log_path(args.session_id)

    content_path = Path(args.content)
    if not content_path.exists():
        print(f"ERROR: content file not found: {content_path}", file=sys.stderr)
        return 2

    body = content_path.read_text(encoding="utf-8")
    ok, missing = _validate_nine_sections(body)
    if not ok:
        msg = "ERROR: missing sections: " + ", ".join(missing)
        print(msg, file=sys.stderr)
        with log.open("a", encoding="utf-8") as f:
            f.write(f"[write_summary] REJECT {content_path} :: {msg}\n")
        return 3

    project_root = locate_project_root(args.project)
    pending = _count_pending(body)
    ide = args.ide or detect_ide()

    if args.dry_run:
        target = build_filename(project_root, ide)
        result = {
            "dry_run": True,
            "would_write": str(target),
            "sections_ok": True,
            "pending_count": pending,
            "ide": ide,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    target = build_filename(project_root, ide)
    frontmatter = build_frontmatter(
        session_id=args.session_id,
        project_root=project_root,
        trigger=args.trigger,
        ide=ide,
        section_word_count=len(body.split()),
        pending_count=pending,
    )
    target.write_text(frontmatter + body.rstrip() + "\n", encoding="utf-8")

    from datetime import datetime
    rel_from_index = target.name
    entry = (
        f"- [{datetime.now().strftime('%Y-%m-%d %H:%M')}] "
        f"[{rel_from_index}]({rel_from_index}) — {args.trigger} · {ide} · 待办: {pending}"
    )
    _update_index(project_root, entry)

    with log.open("a", encoding="utf-8") as f:
        f.write(f"[write_summary] OK {target}\n")

    result = {
        "written": str(target),
        "sections_ok": True,
        "pending_count": pending,
        "ide": ide,
        "trigger": args.trigger,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
