# P0 探针结果

执行环境：Python 3.11+；项目直接依赖精确锁定在 [`backend/requirements.lock`](../backend/requirements.lock)。

| 探针 | 自动化证据 | 当前结论 |
|---|---|---|
| S1 本地嵌入式 seekdb | `test_direct_sdk_gateway_uses_empty_host_for_embedded_seekdb` | 已验证直接 SDK 在嵌入式模式使用空 host、本地路径、嵌入模型配置与 case/agent 范围；须填写 `EMBEDDING_*` 后做真实服务验收。 |
| S2 agent 隔离 | `test_password_script_proves_private_then_public_visibility` | 通过。 |
| S3 case 隔离 | `test_case_isolation_blocks_cross_case_publication` | 通过。 |
| S4 公告板副本 | `test_publish_is_idempotent_and_keeps_one_board_copy` | 通过；原卡保留，副本带来源。 |
| S5 SDK schema | `test_direct_sdk_gateway_uses_oceanbase_mysql_compatible_config_and_scope` | 通过受控 PowerMem SDK 验证 OceanBase/MySQL 兼容连接参数和 case/agent 作用域；真实服务待配置后回归。 |
| S6 DeepAgents 无工具角色 | `python -m app.smoke_deepagents`、`test_deepagents_role_responder_is_tool_free_and_returns_grounded_evidence` | 通过：构造并调用了本地 fake role，模型可见工具集和工具调用均为空，返回已校验的 JSON。 |
| S7 无 LLM 降级 | `test_password_script_proves_private_then_public_visibility` | 通过。 |

DeepAgents 探针与生产角色适配器均使用无工具 Harness Profile；生产角色只接收服务端筛选后的 evidence packet，任何越界引用或调用失败都会自动回退到确定性 responder。

离线验证不会伪装为云端验收。待用户填写 seekdb、LLM 与 embedding 配置后，需运行真实 memory smoke、Docker readiness 与 20 局彩排；详见 [`VALIDATION.md`](./VALIDATION.md)。
