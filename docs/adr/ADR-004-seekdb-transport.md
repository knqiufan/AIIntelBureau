# ADR-004：seekdb 使用 PowerMem SDK 直连与嵌入式切换

背景：部署环境已有云端 seekdb，开发/断网场景需要本地嵌入式 seekdb。

选择：默认 `SEEKDB_MODE=oceanbase`，在应用进程内通过安装的 PowerMem SDK 和 pyobvector 直接访问云端 OceanBase/seekdb 的 MySQL 兼容端口；`embedded` 时同一 SDK 以空 host 打开本地 seekdb。统一 Gateway 不泄漏给业务层，也不部署或调用 PowerMem HTTP Server。

后果：记忆事实源是 PowerMem/seekdb；SDK 的远端连接使用最小数据库凭据，密码只从 `.env` 读入并仅保留在进程内。案件/审计账本继续使用本地持久化 SQLite，以保持事件顺序和演示恢复不依赖向量表结构。

回退：单机展台改为 `SEEKDB_MODE=embedded` 与本地 volume。
