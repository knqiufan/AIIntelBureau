# 验证与现场交接

## 已完成的离线验证

- 后端：`python -m pytest`（38 项）、`python -m app.smoke_memory --in-memory`、`python -m app.rehearse --in-memory --runs 20`、`python -m app.smoke_deepagents`。
- 已在离线 fake model 下验证 DeepAgents 角色运行时：没有模型可见工具，只能引用服务端传入的 evidence packet；不合格输出回退到确定性回答。
- 前端：类型检查、3 条单元测试、生产构建、10 条 Playwright 路径；其中包含 P1 JSON fixture 的可控 mock 事件源、1440×900 与 1920×1080 操作台截图及横向溢出检查、四步引导的刷新恢复及双端同步。
- 可选活动口令：独立浏览器用例验证输入口令后建立 HttpOnly Cookie 会话，操作端和同浏览器上下文的大屏端均可访问受保护 API/SSE。
- 离线录屏：`npm run record:demo` 产出本地 WebM，脚本和四幕台词见 [`recording.md`](./recording.md) 与 [`runbook.md`](./runbook.md)。
- PowerMem Python SDK 适配器：以受控 SDK 验证 OceanBase/MySQL 兼容连接参数、嵌入式空 host、`case:<case_id>` 与 `agent_id` 的隔离参数。
- P3：请求 ID 会回传为 `X-Request-ID`，并贯穿 trace、领域事件和结构化日志；领域事件、日志与 `/api/metrics` 不保留自由耳语/问题全文。
- 自由耳语会拒绝明显的手机号、身份证号以及 `.env` 配置的敏感词；拒绝响应不会回显原文，也不会写入事件账本。
- `DEMO_DATA_RETENTION=ephemeral` 已由测试覆盖：应用退出时先删除 PowerMem 中对应 case 的卡片，再清空本地 SQLite 账本；`python -m app.clear_demo_data` 提供同一作用域的 dry run 与 `--confirm` 人工清理。

## 等待配置后的实机验收

复制 `.env.example` 为 `.env`，再填写：

```dotenv
SEEKDB_HOST=your-seekdb-host
SEEKDB_PORT=2881
SEEKDB_USER=root@tenant#cluster
SEEKDB_PASSWORD=...
SEEKDB_DATABASE=ai_intel_bureau
LLM_API_KEY=...
EMBEDDING_API_KEY=...
EMBEDDING_MODEL=...
DEMO_MODE=full
```

默认 `SEEKDB_MODE=oceanbase`。`SEEKDB_HOST/PORT/USER/PASSWORD/DATABASE` 是 PowerMem SDK 直连云端 OceanBase/seekdb 的 MySQL 兼容参数，不经过 PowerMem HTTP Server。若要测试本地嵌入式 seekdb，则设置 `SEEKDB_MODE=embedded` 并填写 `EMBEDDING_*` 与本地路径配置。

配置完成后，按顺序执行：

```powershell
cd backend
python -m app.preflight --strict
python -m app.preflight --check-remote
python -m app.smoke_memory
python -m app.rehearse --runs 20
cd ..
docker compose up --build
```

然后确认 `/api/readyz` 成功，运行主剧本 A，并分别检查：侦探公开前未知、线人私有命中、公开后侦探仅命中公告板副本。

## 本机限制

本工作区未安装 Docker，因而 Docker Compose 的 YAML/构建文件已准备并由 CI 覆盖构建步骤，但本机尚未执行容器启动；云端 OceanBase/seekdb、StepFun LLM/embedding 也尚未填入凭据，因此尚未进行真实服务调用。
