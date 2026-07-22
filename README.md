# AI 情报局

这是一个 60–90 秒可玩完的 PowerMem 多 Agent 记忆隔离演示：局长把虚构情报写给某个角色；其他角色在公开前检索不到它；局长显式复制到公告板后，其他角色才可检索到公开副本。

项目已完成 P0–P3：

- P0：依赖探针、受限作答边界、配置和 smoke 脚本；
- P1：FastAPI、案件/角色隔离、公开幂等、检索 trace、SSE 回放、降级作答；
- P2：React 操作端与只读大屏端、四步引导、无障碍焦点、reduced-motion、E2E 用例；
- P3：Docker Compose、健康/readiness、预热、日志轮转、20 局彩排脚本、故障手册与 CI。

P4 高级协作实验室（公开审计、仅公开材料的双子 Agent 分析、隔离反面教材和 NativeShare 评估）已作为逐项 feature flag 交付；它不会替代主路径的公告板复制。部署开关、边界与验收状态见 [`docs/P4_RESULT.md`](./docs/P4_RESULT.md)。

## 首先配置

复制 [`.env.example`](./.env.example) 为 `.env`，所有需要你填写或切换的运行参数都在这个文件中。

还提供三个仅含覆盖项的配置 profile：`.env.development.example`（嵌入式 seekdb 开发）、`.env.test.example`（无网络内存/mock 调试）和 `.env.degrade.example`（现场证据模式）。先复制完整的 `.env.example`，再把所选 profile 的值合并进去；运行时始终只读取根目录 `.env`。

默认是远端 OceanBase / seekdb 的 MySQL 兼容直连；PowerMem SDK 已作为后端依赖安装在本项目内：

```dotenv
SEEKDB_MODE=oceanbase
SEEKDB_HOST=your-seekdb-host
SEEKDB_PORT=2881
SEEKDB_USER=root@tenant#cluster
SEEKDB_PASSWORD=...
SEEKDB_DATABASE=ai_intel_bureau
```

这里的 `HOST/PORT/USER/PASSWORD/DATABASE` 会传给 PowerMem 的 `pyobvector` OceanBase 驱动，使用 MySQL 兼容的 `mysql+oceanbase` 连接方式；项目不会调用 PowerMem HTTP API，也不需要 PowerMem Server。`SEEKDB_USER` 可能需要包含租户/集群信息，请使用服务器实际接受的用户名。若切到本地模式，则把 `SEEKDB_MODE` 设为 `embedded`。

切到本地嵌入式 seekdb：

```dotenv
SEEKDB_MODE=embedded
SEEKDB_PATH=./data/seekdb
EMBEDDING_API_KEY=...
EMBEDDING_MODEL=你的嵌入模型
EMBEDDING_DIMENSIONS=模型输出维度
```

LLM 与嵌入模型均为 OpenAI 兼容协议。默认 LLM 已预设为 StepFun `step-3.7-flash`，base URL 为 `https://api.stepfun.com/step_plan/v1`；仅需填 `LLM_API_KEY`。嵌入模型也使用同一协议、base URL 和独立的 `EMBEDDING_*` 配置。嵌入模型名与维度不能安全猜测，因此留给你按服务端实际能力填写。

硅基流动 `BAAI/bge-m3` 可保留 `EMBEDDING_PROVIDER=openai`；`EMBEDDING_BASE_URL` 必须填 API 根路径 `https://api.siliconflow.cn/v1`，并设置 `EMBEDDING_PASS_DIMENSIONS=false`。该模型输出固定 1024 维，`EMBEDDING_DIMENSIONS=1024` 仍用于创建 SeekDB 向量列，但不会作为 API 请求的 `dimensions` 覆盖参数发送。也可将 provider 改为 `siliconflow` 使用 PowerMem 的专用适配器。

在填密钥前保持 `DEMO_MODE=degrade`：游戏仍会提供确定性“知道/不知道”回答，但远端或本地记忆服务尚未配置时不会创建新局。这是刻意的 readiness 保护。

填完 `.env` 后，先在不调用网络的情况下检查配置：

```powershell
cd docs/my/demo/ai_intel_bureau/backend
python -m app.preflight --strict
```

确认后才使用 `python -m app.preflight --check-remote` 初始化 SDK 并验证 OceanBase/seekdb 连通性；两条命令都不会输出密钥。

自由耳语仅用于虚构情报。后端始终拒绝明显的手机号和身份证号模式；`DEMO_DISALLOWED_WHISPER_TERMS` 可在 `.env` 中追加活动现场不允许的词，`DEMO_WHISPER_RATE_LIMIT_PER_MINUTE` 控制每案件、每角色一分钟内的写入上限。拒绝内容不会写进日志或 SSE 事件。

若通过公网展示，设置非空的 `DEMO_ACCESS_KEY`，操作端和大屏端会要求活动口令，受保护 API 和 SSE 也会校验它；健康检查仍可访问。浏览器用口令头换取 HttpOnly 会话 Cookie，SSE URL 不包含口令。请将 Compose 部署在提供 HTTPS 的反向代理或负载均衡器之后，并设置 `DEMO_ACCESS_COOKIE_SECURE=true`；不要把 `.env` 或口令放进前端构建产物。

## 本地开发

后端：

```powershell
cd docs/my/demo/ai_intel_bureau/backend
python -m pytest
python -m app.smoke_memory --in-memory
python -m app.rehearse --in-memory --runs 20
python -m uvicorn app.main:app --reload --port 8000
```

前端（另开一个终端）：

```powershell
cd docs/my/demo/ai_intel_bureau/web
npm ci
npm run dev
```

若只需离线开发或排版，可在根目录 `.env` 设置 `VITE_DEMO_DATA_SOURCE=mock`。这会使用 `web/src/fixtures/p1-password.json` 和 `VITE_MOCK_EVENT_DELAY_MS` 指定的事件回放时钟，不会连接 API、PowerMem、SeekDB 或 LLM；默认值仍是 `api`。

打开 `http://localhost:5173` 会自动创建局长操作端；同一案件的大屏地址为 `http://localhost:5173/stage/<case_id>`。生产代理下由 Nginx 同源提供，两端使用 `/operate/<case_id>` 和 `/stage/<case_id>`。

## Docker 一键启动

配置好 `.env` 后，在本目录执行：

```powershell
docker compose up --build
```

访问 `http://localhost:8080`。API 的 `/api/readyz` 只会在记忆服务可用、预热通过时返回成功；`/api/healthz` 会分别报告 API、PowerMem、seekdb 与 LLM 状态。LLM 未配置时 health 为黄灯（证据模式），不会妨碍隔离演示。

## 验收主路径

1. 加载 `A · 保险箱密码`；
2. 问侦探密码，看到 `侦探 + 公告板` 检索范围及空命中；
3. 问线人密码，看到线人私有卡命中；
4. 选中该私有卡并公开，看到公告板副本与来源，私有原件仍在；
5. 再问侦探，看到只命中公告板副本。

更多交付与边界决定请见 [`docs/`](./docs/)，现场恢复步骤见 [`docs/runbook.md`](./docs/runbook.md)。
