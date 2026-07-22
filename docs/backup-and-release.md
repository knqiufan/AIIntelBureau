# 备份、恢复与发布

## 数据边界与目标

- `persistent`：本地 SQLite 账本的目标 RPO 为 24 小时、RTO 为 60 分钟；每次发布前及每日备份。
- `ephemeral`：不承诺恢复；退出清理失败会保留本地账本和待清理任务，直到人工重试成功。
- 远端 OceanBase/seekdb：由平台团队按其原生快照/导出能力备份。应用不把远端卡片正文复制进 SQLite；恢复时须先恢复远端数据，再恢复 SQLite 账本并执行只读 smoke。
- 嵌入式 seekdb：在应用停机后，与 SQLite 备份处于同一受控加密存储位置；不得把备份或日志上传到仓库。

## SQLite 操作

停掉写入 API 后执行：

```powershell
cd backend
python -m app.backup_state backup --source ../data/ai_intel_bureau_state.sqlite3 --destination ../backups/state-YYYYMMDD.sqlite3
python -m app.backup_state restore --source ../backups/state-YYYYMMDD.sqlite3 --destination ../data/ai_intel_bureau_state.sqlite3 --confirm
```

命令会执行 SQLite `integrity_check` 并输出 SHA-256。恢复会先写入同目录暂存文件，校验通过后才替换目标。演练必须记录开始/结束时间、校验和、远端恢复状态、负责人和复盘链接。

## 发布与回滚

1. 仅从通过 CI 的提交创建带注释 Git tag，例如 `v0.1.1`；发布记录包含 commit SHA、镜像 digest、SBOM、依赖审计和 smoke 结果。
2. 将镜像推送为不可变 tag 与 digest，在 staging 运行 `/api/readyz`、剧本加载、发布、reset 和 SSE 重连 smoke。
3. 若失败，停止新版本并以先前已验证的 tag/digest 回滚；不要覆盖已有 tag。
4. 发布、恢复和数据删除均需记录负责人、审批、时间线及后续复盘。生产分支规则必须要求 `CI quality gates` 和 `Security checks` 成功，且禁止直接绕过。
