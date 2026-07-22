# P4：高级协作实验室交付说明

P4 已实现为独立、可关闭的高级实验室；P1–P3 的“私有记忆 → 局长显式复制 → 公告板副本”主路径未替换。

## 已交付能力

| 能力 | API / 界面 | 安全边界 | 默认值 |
| --- | --- | --- | --- |
| 公开审计时间线 | `GET /api/cases/{case_id}/audit` | 只投影 `memory.published` 事件；不枚举或检索私有空间 | 开启 |
| 公开材料分析 | `POST /api/cases/{case_id}/board-analysis` | `BureauAnalyst` 的两个无工具子 Agent 只收到公告板搜索结果 | 关闭 |
| 反面教材 | `POST/DELETE /api/advanced/unsafe-fixture` | `unsafe_global_search` 只作用于进程内虚构 fixture；不导入正式 Gateway | 关闭 |
| 原生共享适配器 | `app/native_share.py` | 与 P1 的 `MemoryGateway` 分离，永远不会被主演示构造 | 关闭 |

## 开关

在 `.env` 设置以下变量；它们均由服务端再次校验，前端状态不构成授权。

```dotenv
DEMO_ADVANCED_FEATURES_ENABLED=true
DEMO_AUDIT_TIMELINE_ENABLED=true
DEMO_BOARD_ANALYSIS_ENABLED=false
DEMO_UNSAFE_FIXTURE_ENABLED=false
DEMO_NATIVE_SHARE_EXPERIMENT_ENABLED=false
```

反面教材还要求 `DEMO_ALLOW_FREEFORM_WHISPER=false`。两者不能同时可用：启动 fixture 后退出会清理该进程内独立 case，不会写入 `demo_events`、PowerMem 或 seekdb。

## BureauAnalyst 边界

`evidence_summarizer` 与 `consistency_reviewer` 是两个固定的 DeepAgents 子 Agent：

- `tools=[]`、`subagents=[]`；不传入 PowerMem、seekdb、文件系统、shell、网络、case ID 或 Gateway；
- 先由服务端执行 `bulletin_board` 作用域检索，再将结果作为唯一 evidence packet；
- 每个事实和风险引用都必须指向该 packet 内的公告板卡；
- LLM 不可用时降级为确定性公开材料整理，仍不改变角色可见范围。

响应始终带有“辅助分析，不改变角色可见记忆”的提示。

## NativeShare 评估

`NativeShareGateway` 只包装 `AgentMemory.share_memory(..., permissions=["read"])`，没有复制回退。它的必测矩阵为：

1. 私有写入 → 原生共享 → 对端检索；
2. 重启 → 对端检索；
3. 撤销 → 对端检索 → 再共享；
4. 失败重试、重复共享和跨 case 隔离。

当前项目中的 AgentMemory 原生 share 持久化与撤销契约尚未全绿，因此该路径保持开发实验，不得切换到活动主演示；公告板复制继续作为稳定模式。

## 验证

后端 P4 用例覆盖审计投影、提示注入下的公开材料边界、隔离 fixture 清理和原生共享 adapter 调用形状。前端在 mock/API 模式下均能展示审计、可编辑审问、公开材料分析状态以及配置受控的实验模块。
