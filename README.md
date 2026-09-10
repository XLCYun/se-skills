# se-skill

一组面向软件工程开发与代码审查的 Skills。

推荐使用 npx skills 安装：
```shell
npx skills add XLCYun/se-skills
```

## swarm-coding

`swarm-coding` 是一套用于快速推进大型开发需求的蜂群开发流程，仅在用户明确要求使用时触发。

它会先澄清需求并生成详细规格，再将工作拆分为带有依赖关系的子 issue，据此安排串行或并行开发。每个子 issue 由独立的 subagent 在 worktree 中实现，并经过代码审查、修正、CI/CD 检查和冲突处理后合入；全部子 issue 完成后，主 issue 才会关闭。

蜂群内部使用三个角色 skill：`queen-mode` 负责澄清、拆分和统筹交付，`drone-mode` 负责协调单个子 issue，`worker-mode` 负责实现具体的 issue 分片。它们由 `swarm-coding` 按角色自动引用，不作为直接使用的入口。

完整的执行流程、Subagent Handoff 约定与模型选择规则见 [skills/swarm-coding](skills/swarm-coding/SKILL.md)。

## Labs

仍在研究和验证、不建议日常安装使用的 Skill 放在 [`labs/`](labs/README.md)。它们不属于正式发布的 `skills/` 集合，接口、行为和输出格式可能随时变化。

`code-quality-audit` 当前位于 [`labs/code-quality-audit`](labs/code-quality-audit/SKILL.md)，仅供开发与评估。
