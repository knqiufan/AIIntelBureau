# ADR-003：受限 DeepAgents 作答与确定性回退

背景：当前环境虽有 DeepAgents 0.5.7，但其默认工具栈包含 task、文件与 shell；角色作答不得拥有文件、网络、shell 或记忆访问能力。

选择：检索后默认确定性作答；仅当 `DEMO_MODE=full` 和 LLM key 已配置时，使用 OpenAI 兼容的 StepFun 模型创建无工具 DeepAgents 角色。角色仅接收服务端筛选后的 evidence packet，严格 JSON 与证据 ID 校验失败即回退。

后果：LLM 不可用不会阻断演示；DeepAgents 的文件、shell、网络与 task 能力均不会暴露给角色。

回退：`AnswerService` 在角色初始化、调用或证据校验失败时立即回退到确定性 responder。
