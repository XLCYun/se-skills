---
name: swarm-coding
description: "蜂群开发，用于快速推进大需求开发，要求先进行需求澄清，然后使用 Subagent Handoff 模式快速推进开发。仅在用户明确要求时使用。"
---

# Swarm Coding

流程如下：
1. 使用 grill-with-docs Skill 澄清需求。确保所有必要信息都已收集。如果已经澄清，进行下一步。
2. 使用 worktree 从当前分支创建一个分支作为主分支
3. 使用 to-spec skill 来生成详细的规格说明，同时创建一个主 issue。
4. 使用 to-tickets skill 拆分为多个子 issue。
5. 分析拆分的子 issue 之间的依赖关系。使用 GitHub 的 blocked by 功能来标记依赖关系。
6. 确定子 issue 开发顺序：根据依赖关系，确定可以并行开发的子 issue，哪些需要串行开发
7. 使用 Subagent Handoff 开发模式
8. 当某一个开发 subagent 完成开发任务后，使用 code-review skill 进行代码审查，根据审查结果要求开发 subagent 进行修改，直到审查通过。
9. 当某一个开发 subagent 代码审查通过后，创建一个合入主分支的 PR，检查是否有 CI/CD 阻塞，是否有冲突，如果有则尝试解决，直到成功合入当前分支，并标志该子 issue 已完成。
10. 当所有子 issue 都完成后，创建一个主分支合回当前分支的 PR，到此开发流程结束。
11. 提示用户 PR 已经创建完成，等待用户确认可以合入。合入后标记主 issue 为完成，并清理 worktree 分支和工作区。

## Subagent Handoff 开发模式

1. 每个 subagent 处理一个子 issue
2. subagent 你需要生成一份详细的 spec 给 subagent。比较复杂可以使用 to-spec skill 生成一份 spec 文档。
3. subagent 需要使用 worktree + implement skill 的方式开发代码

### 开发 subagent 的模型偏好

1. 如果用户显式指定了要使用的模型，则使用用户指定的模型
2. 如果用户没有指定，则检查 AGENTS.md 或 CLAUDE.md 中是否有蜂群开发配置指定的开发 subagent 模型偏好，如果有，则按该偏好来。

此规则只对子 issues 的开发 subagent 有效。

### goal 模式

如果 goal 模式或者 ralph loop 模式可用，我们的目标就是完成所有子 issues 的开发和合入，最终标记主 issue 已完成。
