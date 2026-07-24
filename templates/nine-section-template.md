# 九段式会话总结模板

> 严格按此模板产出，用于跨 session / 跨 IDE 复用当前工作。
> 模板源自 Claude Code 官方 `BASE_COMPACT_PROMPT`。
> **原则**：只写 transcript 里实际发生过的事，不脑补、不概述掉细节、不遗漏用户消息。
> **信息密度优先**：每段务求紧凑，能一行说清就不多写；但绝不为省 token 丢关键事实。

---

## 通用规则

- 所有 9 段**必须**存在，即使内容为空也保留标题 + `_（无）_`；缺段会被 `write_summary.py` 拒收。
- 段落顺序不可调换。
- §6 是防漂移锚点：**逐字保留**所有非 tool-result 用户消息。**除 §6 外，任何段落都不要再重复引用用户原话**——因为 §6 已经有完整原话，重复只会耗 token。
- §9 必须**引用最近一条用户消息**作为下一步依据；没暗示下一步就写 `待用户确认`，不要编。
- 代码片段只贴 load-bearing 的极短片段（3-10 行），标语言。不要贴整个函数。
- 文件路径写绝对路径或项目相对路径，禁止只写文件名。
- **禁止在 §1-§8 使用「来自：xxx」这类溯源标注**——§6 已经承担全部溯源职责。

---

## 段落定义（对齐 Claude Code 官方 compact 风格）

### ## 1. Primary Request and Intent / 首要请求与意图

先用**一段 2-4 行的叙述**说清用户想干什么，含核心目标 + 会话演进阶段。
然后可选加**极简 bullet 列出请求的重大转折**（不是每条请求都列，只列真正改变方向的那几条）。
**语言**：叙述用**英文**（或用户会话主要语言的**单一语言**），不要中英文重复对照。
**禁止溯源**：不要写「来自：xxx」；用户原话在 §6 里查即可。

### ## 2. Key Technical Concepts / 关键技术概念

`**名称**: 一句话说清它在本会话中做什么`
每条一行，紧凑到极致。只列真的用到的技术，不列泛泛的概念。

### ## 3. Files and Code Sections / 文件与代码片段

每个文件一条，格式紧凑：
```
- <path> (CREATED|MODIFIED|READ|DELETED)
  - <关键点 1>
  - <关键点 2>
```
若确有非贴不可的 load-bearing 代码（比如唯一体现关键决策的 3-5 行），才用 fenced code block。默认不贴。

### ## 4. Errors and Fixes / 错误与修复

每错一行：`**<症状简述>**: <触发条件>. Fixed by <修复方式>.`
如果是用户口头纠正的，把用户关键词嵌进去（例："user pointed out X")；不要整句抄——完整原话在 §6。
仍未解决的写 `Not yet fixed`。

### ## 5. Problem Solving / 问题解决过程

只写有**实质推理链**的问题，不写"改代码 → 成功"这种流水。
两小类：
- **Solved**: <问题> → <关键决策/折衷>
- **In flight**: <问题> → <当前思路/卡点>

如果本会话没有值得写的推理链，直接写 `_（无）_`。

### ## 6. All User Messages / 所有用户消息

**逐字**列出所有非 tool-result 用户消息，按时间顺序。
每条用 `> ` 引用块保持原样（错别字、口语、断句都保留）。
**这是全文档唯一的原话锚点，其他段落都依赖这一节存在。**

### ## 7. Pending Tasks / 待办任务

用户明确要求但**尚未完成**的事。每条一行，动词开头。
如果没有待办，写 `_（无）_`。**不要**把"下一步猜测"塞进来——那属于 §9。

### ## 8. Current Work / 当前工作

**2-4 行**说清压缩前那一刻你在做什么：哪个文件、哪一步、卡在哪。
最后一轮是新提问就写：`Responding to user's latest message: <一句话概括>`。
不要重述整个上下文，向最近几轮加权。

### ## 9. Optional Next Step / 下一步（可选）

一行搞定，两种模板任选：

```
Based on user's latest message ("<原话截取>"), next: <具体动作>.
```

或（最近消息未暗示下一步）：

```
Latest user message ("<原话截取>") doesn't specify next step; awaiting user.
```

**只截取最相关的几个词**做引用，不要抄整句——完整原话在 §6。禁止在此段发明用户没要求的任务。

---

## 反面模式（严禁）

- ❌ 每条 §1 后面挂"（来自：第 N 轮）"——§6 已完整保留
- ❌ §6 逐字消息之外，其他段落再次抄原话——重复即浪费
- ❌ §3 贴整个文件或大段代码——只贴决策相关的 3-5 行
- ❌ §4 把用户吐槽一整段抄进来——一句话概括+关键词
- ❌ §8 重述整个会话——只写当前那一刻

---

## Mini-Example（示范风格，不要照抄内容）

```markdown
## 1. Primary Request and Intent / 首要请求与意图

User is building session-summarizer, a cross-IDE plugin that generates a 9-section
summary before context auto-compacts. The conversation evolved through phases:
- Initially: plan the plugin, decide between slash-command vs skill vs plugin form
- Then: productize with npm CLI + auto-merge; publish to GitHub public
- Then: fix cross-platform paths (Windows→Mac), support Claude Internal fork
- MOST RECENT: verify Cursor's preCompact behavior on latest version, decide
  to keep Cursor status quo and document the limitation instead of implementing
  the stop-hook + SQLite workaround

## 2. Key Technical Concepts / 关键技术概念

- **PreCompact hook**: Fires before auto-compaction on Claude Code family
- **Cursor preCompact**: Observe-only per Cursor docs; only accepts user_message
- **{{PLUGIN_ROOT}} placeholder**: Replaced at install time for cross-OS paths
- **Claude Internal**: Tencent's fork, uses ~/.claude-internal/ separate home dir

## 3. Files and Code Sections / 文件与代码片段

- D:/.agents/plugins/session-summarizer/scripts/precompact_hook.py (CREATED, then MODIFIED 3×)
  - Added --host cursor branch: emit user_message instead of additionalContext
  - Windows utf-8 stdout forced via sys.stdout.reconfigure
- D:/.agents/plugins/session-summarizer/lib/merge.mjs (CREATED, then MODIFIED)
  - Flavor param: "claude" (nested) vs "cursor" (flat + version:1)
- D:/.agents/plugins/session-summarizer/README.md (REWRITTEN 3×)
  - Added IDE support matrix + Cursor limitations section per user feedback

## 4. Errors and Fixes / 错误与修复

- **Windows gbk stdout crash on CJK template**: precompact_hook.py emit failed. Fixed by sys.stdout.reconfigure(encoding="utf-8").
- **Symlink not followed by Claude Code on Windows**: /session-summarizer invisible. Fixed by switching installer to copy-only.
- **Wrong assumption "Codex has no preCompact"**: user pointed out screenshot proves it does. Fixed by adding claude-internal target and updating plan.

## 5. Problem Solving / 问题解决过程

- **Solved**: Cursor auto-summary path → researched stop hook + SQLite, rejected due to undocumented schema; documented limitation in README instead.
- **Solved**: Plugin form choice → skill+hook rejected because Cursor's skill support is partial; slash-command+hook chosen for max compatibility.

## 6. All User Messages / 所有用户消息

> 现在有一个新的需求，就是我现在想做一个plugin/skill...（完整原话）
> 你怎么做调研的？睁眼看看codex有没有precompact这个hook
> 那么cursor就维持现状吧，你更新一下readme说明一下cursor的特殊情况

## 7. Pending Tasks / 待办任务

- Verify auto PreCompact on CodeBuddy/WorkBuddy/Codex Desktop real usage
- Trust the Codex hook script on first /hooks panel visit
- Consider opt-in stop-hook flag for Cursor if users request it

## 8. Current Work / 当前工作

Just finished pushing README updates (commit e100c9d) explaining Cursor's observe-only
limitation. User then invoked /session-summarizer to test the manual summary path.
Responding to user's latest message: apply three improvements (shorter filename,
tighter template per Claude Code official style, fix write_summary.py gbk bug).

## 9. Optional Next Step / 下一步

Based on user's latest message ("都解决了之后进行推送"), next: apply the three fixes and push to GitHub in one batch.
```
