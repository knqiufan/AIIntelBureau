# P1-007：发布幂等性与进程内状态无法安全扩展

- 状态：Closed（2026-07-23）
- 分类：并发 / 部署拓扑
- 优先级：P1

## 已证实证据

- `backend/app/services.py:105` 的 `_command_lock` 是单进程 `RLock`；
  `publish()` 先查询事件账本、再写远端、最后追加事件（281-304）。
- `backend/app/repository.py:81-87` 通过遍历事件实现 publication 查找，表中没有
  `(case_id, source_memory_id)` 唯一约束或独立 publication 表。
- `_last_answers`、耳语限流与 HTTP metrics 都是进程内字典/计数器
  （`services.py:106-107`、`observability.py:16-38`）。

## 影响

默认单 uvicorn 进程下大多可工作，但多 worker、滚动发布或水平扩容时，两实例可同时
发布同一来源卡，生成多个公开副本；限流、答案和指标也会出现分裂。

## 修复方案

1. 显式声明单副本运行约束，或把案件写模型迁至可共享的数据库事务。
2. 建立 publication 表，并对 `(case_id, source_memory_id)` 创建唯一索引；
   使用插入冲突处理实现跨进程幂等。
3. 将限流、会话、最新视图与指标分别迁移到合适的共享存储/观测系统，不复用进程内对象。
4. 设计远端公开写入与本地唯一记录的失败补偿，避免“已写远端但未记账”。

## 验收标准

- 两个 worker 并发 publish 相同 source 时，最终恰有一个公开副本和一条 publication 记录。
- 任意实例均可读取一致的限流/案件状态；滚动重启不会重复公开。
- 部署文档注明支持的副本数、锁范围和升级路径。
- 并发集成测试在真实 SQLite/目标数据库语义下运行，而不仅是单进程 mock。

## 取舍

如果项目永久只用于单机现场演示，可保留单进程并在 Compose/README 强制限制副本数；
但仍应实现数据库唯一约束，以防未来配置漂移。该项与 P2-002、P2-003 联动。

## 修复记录

`demo_publications` 以 `(case_id, source_memory_id)` 为唯一键实现跨 worker 幂等，并用 pending/ready saga 恢复远端成功、本地未完成窗口；失败删除公共副本或保留补偿任务。复测：双服务实例并发发布测试。
