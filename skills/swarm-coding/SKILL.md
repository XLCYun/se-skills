---
name: swarm-coding
description: "蜂群开发，用于快速推进大需求开发，要求先进行需求澄清，然后使用 Subagent Handoff 模式快速推进开发。仅在用户明确要求时使用。"
---

# Swarm Coding

## 角色定义

1. 蜂王：用户明确调用此 skill 的 agent 即为蜂王。负责澄清需求，规划雄蜂 subagent 的开发顺序。在主分支上工作。
2. 雄蜂：蜂王的 subagent，负责一个 issue 的实现，协调工蜂进行 issue 分片的开发
3. 工蜂：雄蜂的 subagent，负责一个 issue 分片的开发

## 流程
1. 先使用 grill-with-docs Skill 澄清需求
2. 使用 worktree 从当前分支切出一个分支作为主分支
3. 使用 to-spec skill 生成详细的规格，同时创建一个主 issue。
4. 使用 to-tickets skill 拆分为多个子 issue。
5. 分析子 issues 之间的依赖关系。使用 GitHub 的 blocked by 功能标记依赖关系。
6. 根据依赖关系，规划子 issues 开发顺序，确定可并行开发的子 issue
7. 使用雄蜂派发模式，尽可能并行开发多个子 issue。
8. 某一雄蜂完成后，创建一个合回主分支的 PR，合回主分支后标志该子 issue 已完成。
9. 当所有子 issue 都完成后，创建一个主分支合回当前分支的 PR。等待用户确认合入，合入后标记主 issue 完成，并清理 worktree 分支和工作区。

## 雄蜂派发模式

1. 一个 subagent（雄蜂） 处理一个子 issue
2. 使用 to-spec skill 生成一份 spec 文档给雄蜂。对 spec 中不确定的地方，使用 grill-with-docs skill 向用户确认
3. 要求雄蜂使用 worktree + drone-mode skill 进行开发

### 节奏调整

1. 每次获得 subagent 反馈后，获取当前时间，每超过半个小时，检查是否陷入反复的修改循环，或者反复执行某类长时间操作，在不降低任务完成质量的前提下，调整推进方式，反馈给雄蜂。
3. 如果必须轮询 subagent 状态，应避免频繁轮询，轮询间隔可逐步退避到 5 分钟。

### subagent 的模型偏好

1. 用户显式指定的优先
2. 检查 AGENTS.md 或 CLAUDE.md 中的蜂群开发 subagent 模型偏好
