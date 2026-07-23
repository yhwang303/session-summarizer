#!/usr/bin/env python3
"""PreCompact hook：注入九段式模板 + 落盘指令，让当前会话模型自己写总结。

I/O 契约（Claude Code / Cursor / CodeBuddy / WorkBuddy / Codex 桌面版共用）：
  stdin  : {"hook_event_name":"PreCompact","session_id":"...",
           "transcript_path":"...","cwd":"...","trigger":"auto"|"manual"}
  stdout : 单个 JSON，含 hookSpecificOutput.additionalContext
  exit   : 出错永远 0，避免打断 IDE

设计约束：
- 只在 trigger == "auto" 时注入；手动 /compact 用户自己知道在做什么，不打扰
- hook 不起 LLM 调用；靠 additionalContext 让主会话模型自己走一遍 slash command
- 任何异常都吞掉，输出 {} + exit 0
"""
from __future__ import annotations

import io
import json
import os
import sys
import traceback
from pathlib import Path

# Windows 默认 stdout 常见是 gbk，强制 utf-8 以避免模板里的 CJK/零宽字符炸掉。
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except (AttributeError, ValueError):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", newline="")

SCRIPT_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = SCRIPT_DIR.parent
TEMPLATE_PATH = PLUGIN_ROOT / "templates" / "nine-section-template.md"
WRITE_SUMMARY = SCRIPT_DIR / "write_summary.py"

sys.path.insert(0, str(SCRIPT_DIR))
from util_paths import detect_ide, locate_project_root, state_log_path  # noqa: E402


def _read_stdin_payload() -> dict:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _emit(obj: dict) -> None:
    """stdout 只允许一个 JSON，其他都写日志。"""
    sys.stdout.write(json.dumps(obj, ensure_ascii=False))
    sys.stdout.flush()


def _log(session_id: str, msg: str) -> None:
    try:
        with state_log_path(session_id).open("a", encoding="utf-8") as f:
            f.write(f"[precompact] {msg}\n")
    except Exception:
        pass


def _build_additional_context(
    template_text: str,
    session_id: str,
    project_root: Path,
    ide: str,
) -> str:
    write_cmd = (
        f'python "{WRITE_SUMMARY.as_posix()}" '
        f'--session-id "{session_id}" '
        f'--project "{project_root.as_posix()}" '
        f'--trigger auto '
        f'--ide "{ide}" '
        f'--content "<你写好的临时 md 路径>"'
    )

    return (
        "SESSION_SUMMARIZER PreCompact HOOK\n"
        "==================================\n"
        "系统即将自动压缩上下文。在压缩发生前，你必须先做一件事：\n"
        "把当前整个会话按下面这份九段式模板产出一份完整总结，落盘到项目级目录。\n"
        "这是为了让用户能跨 IDE / 跨 session 复用当前工作，避免默认压缩丢失关键信息。\n\n"
        f"当前 session_id: {session_id}\n"
        f"当前项目根: {project_root.as_posix()}\n"
        f"当前 IDE: {ide}\n\n"
        "---\n"
        "步骤：\n"
        "1) 严格按下面模板产出九段式内容（不要输出到聊天窗口，直接用 Write 工具写到\n"
        "   一个临时 .md 文件里，例如 %TEMP%/session-summary-<session_id>.md）。\n"
        "2) 调用 write_summary.py 落盘并更新 index：\n"
        f"   {write_cmd}\n"
        "3) 落盘成功后，简短告诉用户结果（文件路径 + 待办数量），然后让系统继续 compact。\n\n"
        "关键约束：\n"
        "- 每段 `## N. Title / 中文` 标题一字不差，否则 write_summary.py 会拒收\n"
        "- §6 逐字保留所有非 tool-result 的用户消息，禁止改写/翻译/概述\n"
        "- §9 必须引用最近一条用户消息原话；没暗示下一步就写「待用户确认」\n"
        "- 不要凭空编造用户没要求过的任务\n\n"
        "---\n"
        "九段式模板全文（严格遵守）：\n\n"
        f"{template_text}\n"
    )


def _parse_host_arg() -> str:
    """Return the host id passed via `--host <name>`, default 'claude'."""
    argv = sys.argv[1:]
    for i, a in enumerate(argv):
        if a == "--host" and i + 1 < len(argv):
            return argv[i + 1].lower()
        if a.startswith("--host="):
            return a.split("=", 1)[1].lower()
    return "claude"


def main() -> int:
    payload = _read_stdin_payload()
    session_id = str(payload.get("session_id") or payload.get("conversation_id") or "unknown")
    host = _parse_host_arg()

    try:
        trigger = str(payload.get("trigger") or "auto").lower()
        if trigger not in ("auto", "manual"):
            trigger = "auto"

        if trigger == "manual":
            _log(session_id, f"skip: manual /compact (host={host})")
            _emit({})
            return 0

        cwd = str(payload.get("cwd") or (payload.get("workspace_roots") or [os.getcwd()])[0])
        project_root = locate_project_root(cwd)
        ide = detect_ide(payload) if host == "claude" else host

        if not TEMPLATE_PATH.exists():
            _log(session_id, f"template missing: {TEMPLATE_PATH}")
            _emit({})
            return 0

        template_text = TEMPLATE_PATH.read_text(encoding="utf-8")

        if host == "cursor":
            # Cursor's preCompact is observe-only: we can't inject additionalContext.
            # Best we can do is surface a user-visible message nudging the manual path.
            usage = payload.get("context_usage_percent")
            usage_str = f"（当前上下文 {usage}%）" if usage is not None else ""
            msg = (
                f"⚠️ Cursor 即将自动压缩上下文{usage_str}。压缩后细节可能丢失。\n"
                f"如果这次会话你还想稍后接盘，请立即运行 /session-summarizer 手动写一份九段式总结到 "
                f"{project_root.as_posix()}/.claude/sessions/。"
            )
            _emit({"user_message": msg})
            _log(session_id, f"emitted cursor user_message (project={project_root})")
            return 0

        # Claude Code / CodeBuddy / WorkBuddy / Codex Desktop shape
        ctx = _build_additional_context(template_text, session_id, project_root, ide)
        _emit({
            "hookSpecificOutput": {
                "hookEventName": "PreCompact",
                "additionalContext": ctx,
            }
        })
        _log(session_id, f"injected additionalContext (host={host}, ide={ide}, project={project_root})")
        return 0

    except Exception:
        _log(session_id, "EXC:\n" + traceback.format_exc())
        try:
            _emit({})
        except Exception:
            pass
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
