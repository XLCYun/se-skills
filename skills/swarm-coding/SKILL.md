---
name: swarm-coding
description: "蜂群开发，用于快速推进大需求开发，要求先进行需求澄清，然后使用 Subagent Handoff 模式快速推进开发。仅在用户明确要求时使用。"
---

# Swarm Coding

流程如下：
1. 先使用 grill-with-docs Skill 澄清需求
2. 使用 worktree 从当前分支切出一个分支作为主分支
3. 使用 to-spec skill 生成详细的规格，同时创建一个主 issue。
4. 使用 to-tickets skill 拆分为多个子 issue。
5. 分析子 issues 之间的依赖关系。使用 GitHub 的 blocked by 功能标记依赖关系。
6. 根据依赖关系，规划子 issues 开发顺序，确定可并行开发的子 issue
7. 使用 Subagent Handoff 开发模式，尽可能并行开发多个子 issue。
8. 某一 subagent 完成后，使用 code-review skill 进行代码审查，根据审查结果要求 subagent 进行修改，直到审查通过。审查通过后，创建一个合回主分支的 PR，合回主分支后标志该子 issue 已完成。
9. 当所有子 issue 都完成后，创建一个主分支合回当前分支的 PR。等待用户确认合入，合入后标记主 issue 完成，并清理 worktree 分支和工作区。

## Subagent Handoff 开发模式

1. 一个 subagent 处理一个子 issue
2. 使用 to-spec skill 生成一份 spec 文档给 subagent
3. 要求 subagent 使用 worktree + implement skill 进行开发，但不进行 code-review

### 节奏调整

1. 每半个小时，检查是否陷入反复的修改循环，或者反复执行某类长时间操作，在不降低任务完成质量的前提下，调整推进方式。
2. 等待 subagent 完成：如果支持 subagent 完成后主动通知主 agent，应使用此方式；如果仅支持轮询 subagent 状态，则轮询间隔应逐步退避到 5 分钟。

### 开发 subagent 的模型偏好

1. 如果用户显式指定了要使用的模型，则使用用户指定的模型
2. 如果用户没有指定，则检查 AGENTS.md 或 CLAUDE.md 中是否有蜂群开发配置指定的开发 subagent 模型偏好，如果有，则按该偏好来。

此规则只对子 issues 的开发 subagent 有效。

### goal 模式

如果 goal 模式或者 ralph loop 模式可用，我们的目标就是完成所有子 issues 的开发和合入，最终标记主 issue 已完成。
