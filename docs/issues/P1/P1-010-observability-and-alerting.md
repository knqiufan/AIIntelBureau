# P1-010：可观测性没有监控、告警和 SLO 闭环

- 状态：Closed（2026-07-23）
- 分类：运维可观测性
- 优先级：P1

## 已证实证据

- `backend/app/observability.py` 提供白名单 JSON 日志与进程内 HTTP 计数；
  `main.py:204-209` 暴露 JSON `/api/metrics`。
- 这些指标在重启或多副本间丢失/分裂，且不符合 Prometheus exposition 格式。
- Compose 仅配置本地日志轮转和 healthcheck（`docker-compose.yml:12-20,35-42`），
  无 scrape、仪表盘、告警、日志汇聚或追踪配置。

## 影响

API 未就绪、SSE 反复断开、错误率升高、远端记忆失败或 LLM 成本异常时，只能人工访问
health endpoint。现场恢复和长期运维没有量化 SLO，也无法定位跨服务请求。

## 修复方案

1. 选择标准栈并实现稳定指标：Prometheus/OpenTelemetry metrics、结构化 stdout 日志、
   可选 tracing；不要把私有请求正文做 label/attribute。
2. 定义仪表盘：请求量与 p95、4xx/5xx、ready 状态、活跃 SSE、检索/LLM 延迟、
   fallback、限流、存储容量与清理任务。
3. 定义告警与升级规则：`readyz` 不可用、错误率、SSE 重连、远端删除失败、
   成本预算和容器重启。
4. 为 request ID/trace ID 建立从代理到 API、远端调用的关联规则与采样策略。

## 验收标准

- 人为使 API/记忆服务不可用时，仪表盘和告警在目标时限内反映并恢复。
- 任意 request ID 可在脱敏日志中关联到状态、耗时和失败类型。
- 重启和多副本后历史指标仍由观测系统保存，非仅内存计数。
- 提供 SLO、告警负责人、静默/演练流程和 runbook 链接。

## 依赖

P1-004、P1-006、P1-008 的配额/清理/重连指标应一并纳入。日志处理须遵从 P0-001，
不得把 SDK 原始 DEBUG 文件重新作为观测方案。

## 修复记录

增加内网 Prometheus `/metrics`（固定脱敏标签）和操作台 JSON 指标，覆盖 HTTP、SSE 与清理待办。`docs/observability.md` 定义仪表盘、SLO、告警、值班和复盘流程。
