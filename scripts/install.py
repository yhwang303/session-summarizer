#!/usr/bin/env python3
"""一键把 slash command 分发到 5 个 IDE 的 commands/ 目录。

不动 hook 注册文件——那些需要用户手动 merge 到自己的 settings.json / hooks.json /
config.toml，避免覆盖用户已有的 hook 配置。

用法：
  python install.py [--dry-run] [--force] [--target <ide>[,<ide>...]]

支持的 IDE key：claude-code, cursor, codebuddy, workbuddy, codex
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = SCRIPT_DIR.parent
SLASH_COMMAND_SRC = PLUGIN_ROOT / "commands" / "session-summarizer.md"
TEMPLATE_DIR = PLUGIN_ROOT / "install-templates"


@dataclass(frozen=True)
class IDETarget:
    key: str
    label: str
    commands_dir: Path
    hook_template: str
    hook_target_hint: str


def _home() -> Path:
    return Path.home()


def _project_cursor_dir() -> Path:
    return Path(os.getcwd()) / ".cursor" / "commands"


def targets() -> list[IDETarget]:
    home = _home()
    return [
        IDETarget(
            key="claude-code",
            label="Claude Code",
            commands_dir=home / ".claude" / "commands",
            hook_template="claude-code.settings.json",
            hook_target_hint="~/.claude/settings.json  (merge into hooks.PreCompact[])",
        ),
        IDETarget(
            key="cursor",
            label="Cursor",
            commands_dir=_project_cursor_dir(),
            hook_template="cursor.hooks.json",
            hook_target_hint="<project>/.cursor/hooks.json  (merge into hooks.preCompact[])",
        ),
        IDETarget(
            key="codebuddy",
            label="CodeBuddy",
            commands_dir=home / ".codebuddy" / "commands",
            hook_template="codebuddy.settings.json",
            hook_target_hint="~/.codebuddy/settings.json  (merge into hooks.PreCompact[])",
        ),
        IDETarget(
            key="workbuddy",
            label="WorkBuddy",
            commands_dir=home / ".workbuddy" / "commands",
            hook_template="workbuddy.settings.json",
            hook_target_hint="~/.workbuddy/settings.json  (merge into hooks.PreCompact[])",
        ),
        IDETarget(
            key="codex",
            label="Codex Desktop",
            commands_dir=home / ".codex" / "prompts",
            hook_template="codex.hooks.json",
            hook_target_hint="~/.codex/hooks.json  OR  ~/.codex/config.toml  (see install-templates/codex.config.toml)",
        ),
    ]


def _install_slash(dst_dir: Path, dry_run: bool, force: bool) -> str:
    dst = dst_dir / SLASH_COMMAND_SRC.name

    if dst.exists() and not force:
        return f"skip (exists): {dst}"

    if dry_run:
        return f"would install: {SLASH_COMMAND_SRC} -> {dst}"

    dst_dir.mkdir(parents=True, exist_ok=True)
    if dst.exists() and force:
        dst.unlink()

    try:
        os.symlink(SLASH_COMMAND_SRC, dst)
        return f"symlinked: {dst}"
    except (OSError, NotImplementedError):
        shutil.copy2(SLASH_COMMAND_SRC, dst)
        return f"copied: {dst}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="Overwrite existing slash command file.")
    parser.add_argument(
        "--target",
        default="",
        help="Comma-separated IDE keys to install. Default: all.",
    )
    args = parser.parse_args(argv)

    if not SLASH_COMMAND_SRC.exists():
        print(f"ERROR: source not found: {SLASH_COMMAND_SRC}", file=sys.stderr)
        return 2

    wanted = {t.strip() for t in args.target.split(",") if t.strip()} or None

    all_targets = targets()
    print(f"session-summarizer install {'(dry-run)' if args.dry_run else ''}")
    print(f"Source slash command: {SLASH_COMMAND_SRC}\n")

    for tgt in all_targets:
        if wanted and tgt.key not in wanted:
            continue
        print(f"[{tgt.label}]")
        print(f"  commands dir : {tgt.commands_dir}")
        print(f"  slash        : {_install_slash(tgt.commands_dir, args.dry_run, args.force)}")

        template_path = TEMPLATE_DIR / tgt.hook_template
        print(f"  hook template: {template_path if template_path.exists() else '(missing)'}")
        print(f"  merge into   : {tgt.hook_target_hint}\n")

    print("Next steps:")
    print("  1. Merge each hook template into the target file listed under `merge into`.")
    print("  2. Restart the IDE so hooks reload.")
    print("  3. For Codex first run: open /hooks and trust the script.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
