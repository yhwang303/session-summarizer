#!/usr/bin/env python3
"""列出当前项目 summary/sessions/ 下所有九段式总结。

用法：
  python list_summaries.py [--project <cwd>] [--json]

默认按 mtime 倒序打印可读列表；--json 输出机器可读列表。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from util_paths import locate_project_root, sessions_dir  # noqa: E402


def _parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    header = text[3:end]
    result: dict[str, str] = {}
    for line in header.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        k, _, v = line.partition(":")
        result[k.strip()] = v.strip().strip("'\"")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default=os.getcwd())
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    project_root = locate_project_root(args.project)
    d = sessions_dir(project_root)

    entries: list[dict] = []
    for path in sorted(d.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
        if path.name == "index.md":
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        meta = _parse_frontmatter(text)
        entries.append({
            "file": path.name,
            "path": str(path),
            "title": meta.get("title", ""),
            "timestamp": meta.get("timestamp", ""),
            "trigger": meta.get("trigger", ""),
            "ide": meta.get("ide", ""),
            "pending_count": meta.get("pending_count", ""),
        })

    if args.json:
        print(json.dumps({"project": str(project_root), "entries": entries}, ensure_ascii=False, indent=2))
        return 0

    if not entries:
        print(f"(no summaries in {d})")
        return 0

    print(f"Project: {project_root}")
    print(f"Sessions dir: {d}")
    print(f"Total: {len(entries)}\n")
    for e in entries:
        print(f"  {e['timestamp'] or '?':<25} [{e['trigger'] or '?':<6}] {e['ide'] or '?':<12} pending={e['pending_count'] or '?':<3} {e['title']}")
        print(f"    -> {e['file']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
