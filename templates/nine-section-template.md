# 九段式会话总结模板

> 严格按此模板产出，用于跨 session / 跨 IDE 复用当前工作。
> 模板来源：Claude Code 官方 `BASE_COMPACT_PROMPT`。
> **原则**：只写 transcript 里实际发生过的事，不脑补、不概述掉细节、不遗漏用户消息。

---

## 通用规则

- 所有段落**必须**存在，即使内容为空也要保留标题 + `_（无）_`；缺段的输出会被 `write_summary.py` 拒收。
- 段落顺序不可调换。
- §6 是防漂移锚点：**逐字保留**所有非 tool-result 的用户消息，不允许改写或概述。
- §9 必须**引用最近一条用户消息**作为下一步依据；如果最近消息里没暗示下一步，就写"待用户确认"，不要编。
- 代码片段用 fenced code block，标语言。
- 文件路径用绝对路径或相对项目根的路径，禁止只写文件名。

---

## 段落定义

### ## 1. Primary Request and Intent / 首要请求与意图

整个会话中用户提出的**所有**显式请求与目标，按时间顺序。
每条一行，形如：`- <描述>（来自：<用户消息片段或轮次>）`。
不要合并请求；同一请求的多次澄清各写一行，让后续 session 能看到需求是如何演化的。

### ## 2. Key Technical Concepts / 关键技术概念

会话中讨论过的技术、框架、模式、库、协议、约定。
每条一行，格式：`- <名称>：<在本会话中扮演的角色>`。
只列真的用到的；不要罗列泛泛的概念。

### ## 3. Files and Code Sections / 文件与代码片段

查看 / 修改 / 创建的每个文件都要出现。
格式：
```
### <绝对路径或项目相对路径>
**动作**：查看 / 修改 / 创建 / 删除
**原因**：<为什么动这个文件>
**关键片段**：
​```<lang>
<load-bearing 片段，不是全文>
​```
```
如果一个文件既查看又修改，合并成一条，动作写"查看 → 修改"。

### ## 4. Errors and Fixes / 错误与修复

每一个报错都要一条，即便最后没解决。格式：
```
- **错误**：<原始报错信息或简述>
  **触发**：<什么操作导致>
  **修复**：<最终采取的修复；如果是用户口头纠正的，把用户原话引在这里>
  **状态**：已修复 / 待修复
```

### ## 5. Problem Solving / 问题解决过程

区分两类：
- **已解决**：<问题> → <关键决策 / 折衷>
- **进行中**：<问题> → <当前思路 / 卡点>

只写有实质推理链的，不写"报错 → 改代码 → 成功"这种琐碎流水。

### ## 6. All User Messages / 所有用户消息

**逐字**列出所有非 tool-result 的用户消息，按时间顺序。
每条一行，用 `> ` 引用块或代码块保持原样，包括错别字、口语。
**这是防止后续 session 漂移的锚点，禁止改写、翻译、概述。**

### ## 7. Pending Tasks / 待办任务

用户明确要求过但**尚未完成**的事。每条一行。
如果没有待办，写 `_（无）_`。
不要把"下一步可能要做"塞进这里；那属于 §9。

### ## 8. Current Work / 当前工作

压缩发生前那一刻，你正在做的具体事情。
向最近几轮加权：写清楚在哪个文件、哪一步、卡在哪里。
如果最近一条是用户新提问，那 "当前工作" 就是"正在响应用户的最新提问：<原话>"。

### ## 9. Optional Next Step / 下一步（可选）

**必须**引用最近一条用户消息作为依据：
```
基于用户最新消息「<引用原话>」，下一步应该：<具体动作>。
```
如果最近一条用户消息没暗示下一步（例如是个纯陈述），就写：
```
最近一条用户消息（「<引用原话>」）未明确下一步，待用户确认。
```
禁止在此段编造用户没要求过的任务。

---

## Mini-Example（示范用，不要照抄进真实输出）

```markdown
## 1. Primary Request and Intent / 首要请求与意图
- 想做一个 session 总结 plugin，支持显式和自动触发（来自：首轮用户消息）
- 自动触发要在系统 compact 前抢先做，避免默认压缩丢信息（来自：首轮）
- 5 个 IDE 全支持：Claude Code / Cursor / CodeBuddy / WorkBuddy / Codex 桌面版（来自：第 4 轮澄清）

## 2. Key Technical Concepts / 关键技术概念
- PreCompact hook：Claude Code 家族在自动压缩前触发的钩子事件
- Anthropic BASE_COMPACT_PROMPT：Claude Code 内部使用的九段式压缩模板
- Slash command：IDE 里 `/xxx` 形式的用户主动入口

## 3. Files and Code Sections / 文件与代码片段
### D:/.agents/plugins/session-summarizer/templates/nine-section-template.md
**动作**：创建
**原因**：作为 hook 和 slash command 共用的模板真相源
**关键片段**：见本文件

## 4. Errors and Fixes / 错误与修复
- **错误**：subagent 误判 Codex 桌面版不支持 PreCompact
  **触发**：subagent 只看了 Codex Rust CLI 源码，没查桌面版文档
  **修复**：用户截图给我看 Codex 桌面版设置里明确有 PreCompact hook 项，plan 更正
  **状态**：已修复

## 5. Problem Solving / 问题解决过程
- 已解决：架构从 skill+hook 简化为 slash+hook，去掉 SKILL.md 中转层
- 已解决：确认 hook 不自己调 LLM，而是通过 additionalContext 让当前会话模型自己写

## 6. All User Messages / 所有用户消息
> 现在有一个新的需求，就是我现在想做一个plugin/skill，用来总结上下文……（原话省略）
> 你怎么做调研的？睁眼看看codex有没有precompact这个hook
> 为什么plugin还需要有一个skill的md文件？剩下ide的json或者toml文件又是什么意思

## 7. Pending Tasks / 待办任务
- 实现 scripts/write_summary.py 的九段校验和 index 更新
- 5 IDE 各跑一次自动触发的真实压缩验证

## 8. Current Work / 当前工作
正在写 templates/nine-section-template.md，作为整个 plugin 的模板真相源。

## 9. Optional Next Step / 下一步
基于用户最新消息「一口气完成 5 IDE 全支持」，下一步应该：继续按 plan 落地顺序写 commands/session-summarizer.md 和 scripts/*.py。
```
