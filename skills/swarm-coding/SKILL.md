---
name: swarm-coding
description: "蜂群开发，用于快速推进大需求开发，要求先进行需求澄清，然后使用 Subagent Handoff 模式快速推进开发。仅在用户明确要求时使用。"
---

# Swarm Coding

此 skill 是蜂群开发的显式入口。用户明确调用后，当前 agent 成为蜂王，并使用 queen-mode skill 统筹开发。

## 角色与 skill

1. 蜂王：当前 agent，使用 queen-mode skill，在主 worktree 中澄清需求、拆分 issue、规划依赖并协调交付
2. 雄蜂：蜂王的 subagent，每个雄蜂负责一个子 issue，使用 drone-mode skill 协调工蜂完成 issue 分片
3. 工蜂：雄蜂的 subagent，每个工蜂负责一个 issue 分片，使用 worker-mode skill 在独立 worktree 中开发

queen-mode 是后续流程的唯一来源；需求澄清、issue 拆分、依赖编排、雄蜂派发、PR 合并与清理均按该 skill 执行。
