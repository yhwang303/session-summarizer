# session-summarizer

> 用 Anthropic 官方九段式模板，在系统自动压缩上下文**之前**完整落盘当前会话。跨 IDE、跨 session、零信息损失。

<p>
  <a href="https://github.com/yhwang303/session-summarizer/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT"></a>
  <a href="README.md">English</a>
</p>

**问题**：会话到约 85% 上下文时，Claude Code（以及所有遵循其规范的 IDE）会自动 compact。默认的压缩摘要是有损的——用户逐字提问、关键代码片段、没解完的 bug 经常直接消失。切换 IDE（Claude Code → Cursor → Codex）或开新 session 时，没有任何东西可以承接。

**这个插件做什么**：注册一个 `PreCompact` hook，在系统真正 compact **之前**触发。它把 Anthropic 官方九段式模板（来自 Claude Code 内部的 `BASE_COMPACT_PROMPT`）注入到模型上下文里，让当前会话的模型**先**按九段式写一份完整总结，落盘到 `<项目>/.claude/sessions/`，然后再让系统继续 compact。

支持 **Claude Code · Cursor · CodeBuddy · WorkBuddy · Codex 桌面版**。

---

## 安装

按你的使用场景选一个。

### 方式 1 · Claude Code 插件市场（Claude Code 用户首选）

在 Claude Code 里输入：

```
/plugin marketplace add yhwang303/session-summarizer
/plugin install session-summarizer@session-summarizer
```

重启 Claude Code。完成。`/session-summarizer` 命令和 `PreCompact` hook 都已就绪。

### 方式 2 · `npx` 一行命令（多 IDE 用户首选）

如果你也在用 Cursor / CodeBuddy / WorkBuddy / Codex：

```bash
npx github:yhwang303/session-summarizer install
```

只装指定 IDE：

```bash
npx github:yhwang303/session-summarizer install --target claude-code,cursor
```

安装器会：

- 把 `/session-summarizer` slash 命令分发到每个 IDE 的 commands 目录
- 把 `PreCompact` hook 智能 merge 到每个 IDE 的 settings 配置文件（JSON 或 TOML）
- 写之前先备份为 `<file>.bak-<时间戳>`
- **幂等**——重复运行不会重复添加条目
- 保留你已有的 hook 配置（只追加带来源标记的自己那一条，不动别人的）

检查安装状态：

```bash
npx github:yhwang303/session-summarizer status
```

卸载（只删自己写入的，其他 hook 原样保留）：

```bash
npx github:yhwang303/session-summarizer uninstall
```

### 方式 3 · 手动（clone + 本地运行）

在无法用 npx 的环境里：

```bash
git clone https://github.com/yhwang303/session-summarizer ~/session-summarizer
cd ~/session-summarizer
node bin/cli.mjs install
```

**环境要求**：Node 18+ 和 Python 3.8+（Python 是 hook 脚本本身需要，不是安装器需要）。

---

## 工作原理

两种触发方式，同一种输出格式：

| 触发方式 | 什么时候触发 | 摘要怎么被写出来 |
|---|---|---|
| **显式** | 你在任意时刻输入 `/session-summarizer` | Slash 命令加载九段式模板，让模型按模板输出，最后调 `write_summary.py` 落盘 |
| **自动** | `PreCompact` 事件——IDE 即将自动压缩之前 | Hook 把模板注入 `additionalContext`；模型按九段式写完，调 `write_summary.py` 落盘，再让 IDE 继续 compact |

不管哪种触发，输出都走同一个路径——这是核心设计：

```
<项目>/.claude/sessions/
├── index.md                                          # 追加式，人类可读
├── 2026-07-23-session-summarizer-plugin-a3f2.md
└── 2026-07-22-eval-dataset-design-1b8c.md
```

每份摘要严格按 Claude Code 官方 `BASE_COMPACT_PROMPT` 的九段结构：

1. **首要请求与意图** — 会话中所有用户显式请求，按时间顺序
2. **关键技术概念** — 实际讨论过的技术、框架、库
3. **文件与代码片段** — 每个动过的文件 + 关键代码片段 + 原因
4. **错误与修复** — 每个报错的处理方式，保留用户原话纠正
5. **问题解决过程** — 已解决 + 仍在排查
6. **所有用户消息** — **逐字保留**，防漂移锚点
7. **待办任务** — 明确要求但未完成
8. **当前工作** — 压缩发生前那一刻正在做的事
9. **下一步（可选）** — 必须引用最近一条用户消息原话

第 6 段是跨 session 复用能安全生效的关键：新 session 拿到摘要文件后能还原你**原本的表述**，而不是一份被概述过的版本。

---

## 跨 IDE 场景演示

```
Session A（Claude Code）                     Session B（Cursor / Codex / 任何 IDE）
─────────────────────                        ─────────────────────────────────────
上下文占用达到 80%                              "读 .claude/sessions/2026-07-23-*.md
      │                                        然后从我上次停下的地方继续"
      ▼
PreCompact hook 触发                                        │
      │                                                     ▼
九段式总结落盘到                                    模型看到 §6（逐字用户消息）
.claude/sessions/                                +  §8（当时在做什么）+ §9（下一步）
      │                                          直接接上，无需重新问背景
      ▼
IDE 继续走默认 compact
```

无论哪个 IDE 触发的总结，输出目录**都固定在** `.claude/sessions/`。这是设计选择——如果每个 IDE 走自己的目录，跨 IDE 复用就不可能了。

---

## 命令

```
session-summarizer <command> [options]

  install     装到所有 IDE（默认），或指定 --target <keys>
  uninstall   移除 session-summarizer 装过的所有东西
  status      显示每个 IDE 的安装状态
  doctor      环境诊断（Node/Python 探测）

Options:
  --target claude-code,cursor,codebuddy,workbuddy,codex
  --dry-run          只打印计划，不动磁盘
  --force            覆盖已存在的 slash 命令文件
  --json             机器可读输出
```

---

## 安全保证

- **绝不破坏你已有的 hook。** merge 时追加一条带 `__source: "session-summarizer"` 标记的条目，你的 hook 原样保留。
- **自动备份**：每次写入前生成 `<file>.bak-<YYYYMMDD-HHMMSS>`。
- **幂等。** 重复 install 会显示 `unchanged`，不会重复条目。
- **卸载精准。** 只删自己写入的那一条。其他你自己配的东西全部保留。
- **Hook 不直接调 LLM。** 它只往 stdout 打印一个 `additionalContext` 字符串，由当前会话的模型自己完成写入。最坏情况（模型忽略指令）也只是回落到默认 compact，不会崩。

---

## 常见问题

**Q：摘要文件存到哪？**
`<项目>/.claude/sessions/`。所有 IDE 都走这个路径——跨 IDE 复用能生效就是靠这一点。

**Q：`.claude/sessions/` 要不要提交到 git？**
自己定。不想入库就加进 `.gitignore`（这个 repo 的 `.gitignore` 已经默认排除）。

**Q：我手动运行 `/compact` 时 hook 会不会触发？**
不会。只监听 `auto` 触发。手动 compact 说明你知道自己在做什么。

**Q：支持 Codex CLI（终端版本，不是桌面版）吗？**
不支持。Codex 的 Rust CLI 没暴露用户级 hook API。Codex 桌面版可以。CLI 用户可以手动跑 `/session-summarizer`。

**Q：自动触发的摘要被截断了怎么办？**
Hook 只注入 prompt，实际写入靠模型。如果触发时上下文已经非常紧张，输出可能不完整。最佳实践：长时间的设计/调试会话，在到 80% 之前手动跑一次 `/session-summarizer` 备份。

**Q：升级后想重新装一次，会不会有问题？**
不会。幂等的。重新跑一遍就能拿到新版本的所有改动。

---

## 参与贡献

Issue 和 PR 都欢迎，仓库地址：[github.com/yhwang303/session-summarizer](https://github.com/yhwang303/session-summarizer)。

提 PR 前请先在本机跑一下 `node bin/cli.mjs install --dry-run`，看下计划输出是否合理。

---

## License

MIT © [yhwang303](https://github.com/yhwang303)
