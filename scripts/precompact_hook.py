#!/usr/bin/env python3
"""PreCompact hook：按宿主分两种行为。

- Claude Code / CodeBuddy / WorkBuddy / Codex Desktop
    stdin  : {"hook_event_name":"PreCompact","session_id":"...",
             "transcript_path":"...","cwd":"...","trigger":"auto"|"manual"}
    stdout : {"hookSpecificOutput":{"hookEventName":"PreCompact",
             "additionalContext":"<九段模板+落盘指令>"}}
    效果   : 模型先按模板写摘要落盘，然后再让宿主继续 compact。可拦截。

- Cursor（通过 CLI 参数 --host cursor 启用）
    stdin  : Cursor preCompact payload（conversation_id / workspace_roots /
             context_usage_percent / is_first_compaction 等，见官方文档）
    stdout : {"user_message":"<提示文字>"}
    效果   : 仅观察型 hook。官方明确 "cannot block or modify the compaction
             behavior"，所以我们只能在压缩发生时显示提示，让用户下次早点手
             动跑 /session-summarizer。additionalContext / decision / block 等
             字段在 Cursor 上都不生效，不要试图注入。

通用规则：
- 只在 trigger == "auto" 时输出，手动 /compact 用户自己知道在做什么
- 出错永远 exit 0，避免打断宿主
- 日志写 ~/.claude/state/session-summarizer/<sid>.log，不占 stdout
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
            # Cursor's preCompact is documented as observe-only:
            #   "This is an observational hook that cannot block or modify the
            #    compaction behavior."
            # (https://cursor.com/docs/agent/third-party-hooks)
            #
            # That means by the time our hook fires, the compaction is already
            # committed and the model can't be re-steered via `additionalContext`
            # (which the doc does not accept anyway — only `user_message` is
            # documented). So we don't try to inject the 9-section prompt here.
            # Instead we surface a user_message pointing at the sessions dir and
            # nudging them to run /session-summarizer *earlier* next time.
            usage = payload.get("context_usage_percent")
            first = bool(payload.get("is_first_compaction"))
            sessions_dir = f"{project_root.as_posix()}/summary/sessions/"

            head = "ℹ️" if first else "⚠️"
            usage_str = f"（上下文 {usage}%）" if usage is not None else ""
            when = "首次自动压缩" if first else "又一次自动压缩"

            msg = (
                f"{head} Cursor 正在执行{when}{usage_str}。\n"
                f"Cursor 的 preCompact 钩子是仅观察型，无法阻塞压缩，"
                f"因此这次的细节可能已经丢失。\n"
                f"想让下次能跨 session 接盘，请在上下文占用约 60-70% 时"
                f"主动跑 /session-summarizer，把九段式总结落盘到：\n"
                f"  {sessions_dir}"
            )
            _emit({"user_message": msg})
            _log(session_id, f"emitted cursor user_message (usage={usage}, first={first}, project={project_root})")
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
