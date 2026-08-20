---
name: swarm-coding
description: "蜂群开发，用于加速大需求开发，要求先进行需求澄清，然后使用 Subagent Handoff 模式快速推进开发。"
---

# Swarm Coding

流程如下：
1. 使用 grill-with-docs Skill 来澄清需求。确保所有必要信息都已收集。如果已经澄清，进行下一步。
2. 使用 to-spec skill 来生成详细的规格说明，同时生成一个主 issue。
3. 使用 to-tickets skill 拆分为多个子 issue，如果用户使用 github，这些子 issue 应创建在主 issue 下。
4. 分析拆分的子 issue 之间的依赖关系。如果用户使用 github，使用 github 的 blocked by 功能来标记依赖关系。
5. 确定子 issue 开发顺序：根据依赖关系，确定可以并行开发的子 issue，哪些需要串行开发
5. 使用 Subagent Handoff 开发模式
6. 当某一个 subagent 完成开发任务后，使用 code-review skill 进行代码审查，如果审查未通过，根据审查结果要求 subagent 进行修改，直到审查通过。
7. 当某一个 subagent 代码审查通过后，创建一个 PR，检查 PR 是否有 CI/CD 阻塞，是否有冲突，如果有则尝试解决，直到成功合入当前分支，并标志该子 issue 已完成。
8. 当所有子 issue 都完成后，标记主 issue 已完成，流程结束。

## Subagent Handoff 开发模式

1. 每个 subagent 处理一个子 issue
2. 你至少需要告知 subagent：
  1. subagent 有可能智力有限但执行力很强，因此你需要生成一份详细的 spec 给 subagent
  2. subagent 需要使用 worktree + implement skill 的方式开发代码

### Subagent 的模型与思考能力偏好

1. 如果用户显式指定了要使用的模型，则使用用户指定的模型
2. 如果用户没有指定，则检查 AGENTS.md 或 CLAUDE.md 中是否有 subagent 的模型偏好，如果有，则按该偏好来。

### goal 模式

如果 goal 模式或者 ralph loop 模式可用，我们的目标就是完成所有子 issue 的开发和合入，最终标记主 issue 已完成。
