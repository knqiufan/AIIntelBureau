# P1-013：备份恢复、发布和项目治理缺失

- 状态：Closed（2026-07-23）
- 分类：交付运营 / 项目治理
- 优先级：P1

## 已证实证据

- Compose 使用持久卷（`docker-compose.yml:8-9,44-45`），默认 SQLite 状态路径为
  持久模式（`settings.py:38-39`），但没有 backup/restore 脚本或演练文档。
- `clear_demo_data` 只处理清理，不是备份恢复；远端 SeekDB 与本地账本没有恢复顺序。
- 版本仅为两个 `0.1.0` 字段；没有镜像 registry、release tag、CHANGELOG 或回滚流程。
- 仓库缺 `LICENSE`、`SECURITY.md`、`CONTRIBUTING.md`、CODEOWNERS 等基础治理文件。

## 影响

卷损坏、误清理或发布失败时无法恢复已知状态；现场部署依赖本机重新构建，无法可靠回滚。
贡献者与漏洞报告人没有清晰入口，依赖许可证也无法判定。

## 修复方案

1. 定义 persistent/ephemeral 两类数据的 RPO/RTO，提供 SQLite、卷和远端记忆的
   备份/恢复顺序、校验和演练脚本。
2. 建立版本化发布：git tag、不可变镜像 tag/digest、变更日志、staging smoke、
   回滚到上一已知良好版本。
3. 补充 `CONTRIBUTING.md`、`SECURITY.md`、LICENSE、支持矩阵和 CODEOWNERS；
   明确私密数据/日志报告渠道。
4. 将 runbook 与 P1-010 告警关联，发布/恢复须有负责人、审批与复盘记录。

## 验收标准

- 在隔离环境演练“删除卷/切换镜像后恢复”，主剧本可在目标 RTO 内恢复且数据一致。
- 任一发布可由 tag/digest 重建，失败可一键回滚；release notes 列出验证结果。
- 新贡献者可按文档完成本地验证；安全报告有不公开披露渠道。
- 许可证、第三方声明和数据保留策略可在 release 中查阅。

## 依赖

备份内容必须先遵从 P0-001 的日志清理和 P1-002 的数据分类。对演示数据可选择不备份，
但应写明这是经过批准的业务决策，而非缺失。

## 修复记录

提供 SQLite 备份/校验和/显式恢复 CLI 与备份、远端恢复、RPO/RTO、发布回滚 runbook。新增 CHANGELOG、LICENSE、SECURITY、CONTRIBUTING、CODEOWNERS 和 Dependabot；CI/分支保护治理要求已记录。
