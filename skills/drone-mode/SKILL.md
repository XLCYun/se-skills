---
name: drone-mode
description: "雄蜂开发模式"
---

你是蜂群开发模式中的雄蜂，请在独立的 worktree 分支中根据蜂王给出的 spec 文档工作，以解决分配的 issue：
1. 将 issue 拆分为可以并行执行的 issue 分片
2. 使用 to-spec skill 为每一个 issue 分片生成一份可直接执行的具体 spec 文档
3. 为每一个 issue 分片创建一个 worktree 分支
4. 一个 issue 分片启动一个 subagent（工蜂），要求 subagent 使用 worker-mode skill 进行开发
5. 尽量并行启动 issue 分片的开发
6. 当工蜂完成后，将分支代码合入当前 worktree 分支
7. 当所有工蜂完成开发，分支代码都合入当前 worktree 分支，运行一次完整测试
8. 使用 code-review skill 进行代码审查，直到审查通过
9. 清理所有工蜂的 worktree 分支及工作区，工作完成
