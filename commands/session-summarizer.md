---
description: 按 Anthropic 九段式模板总结当前会话，落盘到 <project>/.claude/sessions/
argument-hint: [--dry-run] [--title "自定义标题"]
allowed-tools: Read, Write, Bash(python:*), Bash(python3:*)
---

你需要按九段式总结当前整个会话，落盘为一份可跨 session / 跨 IDE 复用的 markdown。

## 第 1 步：加载模板

用 Read 工具读取以下文件，严格遵守其中所有规则（尤其是 §6 逐字保留用户消息、§9 必须引用最近一条用户消息）：

```
{{PLUGIN_ROOT}}/templates/nine-section-template.md
```

## 第 2 步：产出九段式内容

按模板 9 个段落顺序完整输出。**不要输出到聊天窗口给用户看**，直接用 Write 工具写到一个临时 .md 文件里：

- macOS / Linux: `/tmp/session-summary-<session_id>.md`
- Windows: `%TEMP%\session-summary-<session_id>.md`

**关键约束**：
- 每段 `## N. Title / 中文` 标题必须一字不差，否则校验会失败
- §6 里逐字保留所有非 tool-result 的用户消息，不要改写、翻译、合并
- §9 必须引用最近一条用户消息原话；如果最近消息没暗示下一步，写"待用户确认"
- 不要凭空编造用户没要求过的任务

## 第 3 步：落盘

调用 write_summary.py 落盘并更新 index。请使用你所在平台可用的 Python 命令（`python3` 优先，其次 `python`）：

```bash
python3 "{{PLUGIN_ROOT}}/scripts/write_summary.py" \
  --session-id "<当前 session_id>" \
  --project "<当前项目根>" \
  --content "<第 2 步的临时文件路径>" \
  --trigger manual \
  --ide "<当前 IDE，例如 claude-code|cursor|codebuddy|workbuddy|codex>"
```

如果用户传了 `--title "xxx"`，把 `--title xxx` 也加上。

如果用户传了 `--dry-run`，**跳过第 3 步**，只把第 2 步生成的文件路径打印给用户，让用户自己检查。

## 第 4 步：确认

落盘成功后向用户简短汇报：
- 文件路径
- 九段是否齐全（write_summary.py 会返回校验结果）
- 待办任务数量（从 §7 计数）
- index.md 已更新

## 参数解析

用户输入 `$ARGUMENTS`。支持：
- `--dry-run`：不落盘
- `--title "任意标题"`：覆盖自动生成的 slug

## 项目根定位

优先用 `git rev-parse --show-toplevel`，失败则用当前 `cwd`。落盘目录固定 `<项目根>/.claude/sessions/`（不要因为 IDE 不同就换目录，跨 IDE 复用是核心诉求）。
