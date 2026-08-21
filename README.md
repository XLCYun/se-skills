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

## code-quality-audit

`code-quality-audit` 将原来的 `bad-smells-skill` 与 `anti-pattern-skill` 合并为一套可量化、可审计的代码质量审查流程。

它覆盖重构坏味道、软件与交付反模式，以及代码、测试、架构、配置和工程实践等维度，共 31 项检查项。适用于审查整个仓库、子系统或变更集，也可用于多个项目之间的横向质量对比。

审查流程结合静态工具与子代理：先由脚本构建审查清单并收集复杂度、重复代码等指标，再按封闭的文件清单分片审查，最后输出可复核的覆盖率、结构化发现、维度评分和总分。

### 模型分工建议

这个 Skill 会扫描**整个仓库**，并将代码按文件与审查单元切分为多个分片。分片审查实例主要按照明确的检查项核对单个文件或小范围代码，可配置为较轻量的模型，以控制全仓审查的成本和耗时。

跨文件审查需要综合全部分片的结构摘要来判断重复条件分发、平行类、数据泥团等问题；最终整体评级也需要在全局视野下作出工程判断。这两类子代理建议使用更强的推理模型，以提高跨模块结论与最终评分的可靠性。

完整的检查标准、输出格式与评分规则见 [skills/code-quality-audit](skills/code-quality-audit/SKILL.md)。
