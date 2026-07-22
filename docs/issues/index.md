# 审计 issue 索引

状态含义见 [README](./README.md)。P1 条目已于 2026-07-23 完成实现和本地复测，详见各条目的修复记录；P0/P2 仍按其自身状态跟踪。

## P0：上线或公开前必须处理

1. [P0-001：已跟踪运行日志与 Git 历史泄露](./P0/P0-001-tracked-runtime-logs.md)
2. [P0-002：快照接口向大屏下发全部私有记忆](./P0/P0-002-private-snapshot-data-exposure.md)
3. [P0-003：生产访问控制默认失效且 API 可绕过代理暴露](./P0/P0-003-production-access-and-api-exposure.md)

## P1：下一轮可靠性与安全建设

1. [P1-001：会话口令留存与 CORS 策略过宽](./P1/P1-001-auth-session-cors.md)
2. [P1-002：自由输入 PII 边界和模型数据出境控制不足](./P1/P1-002-data-intake-and-model-egress.md)
3. [P1-003：反向代理安全基线和 SSE 存活机制缺失](./P1/P1-003-proxy-security-and-sse-liveness.md)
4. [P1-004：HTTP、LLM 与 SSE 缺少资源配额](./P1/P1-004-request-resource-limits.md)
5. [P1-005：剧本切换和加载失败破坏案件一致性](./P1/P1-005-script-lifecycle-transaction.md)
6. [P1-006：重置、审计与远端清理语义不一致](./P1/P1-006-reset-audit-and-cleanup-consistency.md)
7. [P1-007：发布幂等性与进程内状态无法安全扩展](./P1/P1-007-publication-idempotency-and-multi-instance.md)
8. [P1-008：SSE 断线从零重放并放大快照请求](./P1/P1-008-sse-resumption-and-backpressure.md)
9. [P1-009：记忆分页、数据保留和容量边界未定义](./P1/P1-009-storage-pagination-retention.md)
10. [P1-010：可观测性没有监控、告警和 SLO 闭环](./P1/P1-010-observability-and-alerting.md)
11. [P1-011：没有实际 CI 和质量门禁](./P1/P1-011-ci-quality-gates.md)
12. [P1-012：依赖供应链与容器构建加固不足](./P1/P1-012-supply-chain-and-container-hardening.md)
13. [P1-013：备份恢复、发布和项目治理缺失](./P1/P1-013-backup-release-governance.md)

## P2：韧性、体验与回归防护

1. [P2-001：409 冲突快照未被前端用于恢复](./P2/P2-001-conflict-recovery.md)
2. [P2-002：最近答案和检索 trace 重启后丢失](./P2/P2-002-answer-state-recovery.md)
3. [P2-003：读写并发和全局案件锁的行为未定义](./P2/P2-003-concurrency-and-case-locks.md)
4. [P2-004：关键安全、故障和真实适配器回归覆盖不足](./P2/P2-004-test-strategy-and-regression.md)

## 依赖顺序

`P0-001` 独立且优先；`P0-002` 是 P1-001、P2-004 的授权测试基础；
`P0-003` 依赖 P1-003 与 P1-004 的部署防护；P1-005、P1-006、P1-007
应共同设计远端记忆和 SQLite 的一致性模型；P1-011 是其余项持续不回归的前提。
